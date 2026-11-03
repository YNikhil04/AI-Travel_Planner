"""Places provider. Google Places (New) when a key is set (ratings, review counts, price level);
otherwise OpenStreetMap via Overpass (no ratings, so popularity is estimated from tags)."""
import math

import httpx

from ..config import settings
from .geo import overpass
from .osm_tags import osm_category, osm_popularity, osm_rating_proxy, stay_tier

GOOGLE_URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ("places.id,places.displayName,places.location,places.rating,places.userRatingCount,"
          "places.priceLevel,places.formattedAddress,places.types")
CAT_QUERY = {
    "culture": "historical places and museums in {c}",
    "nature": "parks, viewpoints and nature spots in {c}",
    "adventure": "adventure activities in {c}",
    "relax": "beaches, lakes and relaxing places in {c}",
    "shopping": "markets and shopping streets in {c}",
    "nightlife": "nightlife and live music in {c}",
}
OUTDOOR_DEFAULT = {"culture": False, "nature": True, "adventure": True, "relax": True, "shopping": False,
                   "nightlife": False}
PRICE_TIER = {"PRICE_LEVEL_FREE": "Budget", "PRICE_LEVEL_INEXPENSIVE": "Budget", "PRICE_LEVEL_MODERATE": "Mid",
              "PRICE_LEVEL_EXPENSIVE": "Luxury", "PRICE_LEVEL_VERY_EXPENSIVE": "Luxury"}


def provider() -> str:
    return "google" if settings.google_places_api_key else "osm"


def _google(query: str, lat: float, lon: float, radius: int = 20000) -> list[dict]:
    body = {"textQuery": query, "pageSize": 20,
            "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius}}}
    r = httpx.post(GOOGLE_URL, json=body, timeout=25, headers={
        "X-Goog-Api-Key": settings.google_places_api_key, "X-Goog-FieldMask": FIELDS})
    r.raise_for_status()
    return r.json().get("places", [])


def _gbase(g: dict) -> dict:
    return {"id": "g:" + g["id"], "name": g["displayName"]["text"], "lat": g["location"]["latitude"],
            "lon": g["location"]["longitude"], "rating": g.get("rating"), "reviews": g.get("userRatingCount"),
            "address": g.get("formattedAddress", ""), "source": "google"}


def _gscore(g: dict) -> float:
    return round(min(5.0, (g.get("rating") or 3.5) * math.log10((g.get("userRatingCount") or 0) + 1) / 4), 2)


def _els(elements: list[dict]):
    seen = set()
    for e in elements:
        t = e.get("tags", {})
        name = t.get("name:en") or t.get("name")
        pos = e if "lat" in e else e.get("center")
        if not name or not pos or name in seen:
            continue
        seen.add(name)
        yield e, t, name, pos


def attractions(lat: float, lon: float, city: str, interests: list[str]) -> list[dict]:
    if provider() == "google":
        out, ids = [], set()
        for cat in dict.fromkeys(list(interests) + ["culture"]):
            for g in _google(CAT_QUERY[cat].format(c=city), lat, lon):
                if "g:" + g["id"] in ids:
                    continue
                ids.add("g:" + g["id"])
                out.append({**_gbase(g), "category": cat, "outdoor": OUTDOOR_DEFAULT[cat]})
        return out
    q = f"""[out:json][timeout:30];(
 nwr["tourism"~"attraction|museum|viewpoint|theme_park|gallery|zoo"]["name"](around:15000,{lat},{lon});
 nwr["historic"~"castle|fort|monument|memorial|archaeological_site|palace|ruins"]["name"](around:15000,{lat},{lon});
 nwr["natural"~"beach|waterfall|peak"]["name"](around:20000,{lat},{lon});
 nwr["leisure"~"park|garden|nature_reserve"]["name"](around:12000,{lat},{lon});
 nwr["amenity"~"marketplace|nightclub"]["name"](around:12000,{lat},{lon});
);out center tags 250;"""
    out = []
    for e, t, name, pos in _els(overpass(q)):
        cat = osm_category(t)
        if cat:
            out.append({"id": f"osm:{e['type']}{e['id']}", "name": name, "category": cat[0], "outdoor": cat[1],
                        "lat": pos["lat"], "lon": pos["lon"], "rating": osm_rating_proxy(t), "reviews": None,
                        "pop": osm_popularity(t), "address": t.get("addr:street", ""), "source": "osm"})
    out.sort(key=lambda p: -p["pop"])
    return out[:60]


def food(lat: float, lon: float, city: str, diet: str) -> list[dict]:
    if provider() == "google":
        out = {}
        queries = [(f"best restaurants in {city}", False)] + ([(f"vegetarian restaurants in {city}", True)]
                                                               if diet == "Veg" else [])
        for q, veg in queries:
            for g in _google(q, lat, lon, 15000):
                cuisine = (g.get("types") or ["restaurant"])[0].replace("_", " ")
                item = out.setdefault("g:" + g["id"], {**_gbase(g), "cuisine": cuisine, "score": _gscore(g),
                                                      "price": PRICE_TIER.get(g.get("priceLevel"), "Mid"),
                                                      "veg": False})
                item["veg"] = item["veg"] or veg or "vegetarian" in cuisine or "vegan" in cuisine
        return list(out.values())
    q = f"""[out:json][timeout:30];(
 nwr["amenity"~"restaurant|cafe"]["name"](around:8000,{lat},{lon}););out center tags 200;"""
    out = []
    for e, t, name, pos in _els(overpass(q)):
        score = 3.0 + (0.8 if t.get("wikidata") else 0) + (0.4 if t.get("cuisine") else 0) + \
                (0.3 if t.get("opening_hours") else 0)
        out.append({"id": f"osm:{e['type']}{e['id']}", "name": name, "lat": pos["lat"], "lon": pos["lon"],
                    "cuisine": (t.get("cuisine") or t.get("amenity", "restaurant")).replace(";", ", "),
                    "rating": None, "reviews": None, "score": round(min(score, 4.5), 2), "price": "Mid",
                    "veg": t.get("diet:vegetarian") in ("yes", "only") or t.get("diet:vegan") in ("yes", "only"),
                    "address": t.get("addr:street", ""), "source": "osm"})
    out.sort(key=lambda f: -f["score"])
    return out[:40]


def stays(lat: float, lon: float, city: str) -> list[dict]:
    if provider() == "google":
        return [{**_gbase(g), "type": "hotel", "tier": PRICE_TIER.get(g.get("priceLevel"), "Mid"),
                 "score": _gscore(g)} for g in _google(f"hotels in {city}", lat, lon, 15000)]
    q = f"""[out:json][timeout:30];(
 nwr["tourism"~"hotel|hostel|guest_house|apartment|resort"]["name"](around:10000,{lat},{lon}););out center tags 150;"""
    out = []
    for e, t, name, pos in _els(overpass(q)):
        score = 3.0 + (0.8 if t.get("wikidata") else 0) + (0.3 if t.get("website") else 0) + \
                (0.3 if t.get("stars") else 0)
        out.append({"id": f"osm:{e['type']}{e['id']}", "name": name, "lat": pos["lat"], "lon": pos["lon"],
                    "type": t.get("tourism", "hotel").replace("_", " "), "tier": stay_tier(t), "rating": None,
                    "reviews": None, "score": round(min(score, 4.5), 2), "address": t.get("addr:street", ""),
                    "source": "osm"})
    out.sort(key=lambda s: -s["score"])
    return out[:40]
