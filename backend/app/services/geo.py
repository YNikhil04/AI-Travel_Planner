"""Geocoding via OpenStreetMap Nominatim (free; respect the 1 request/second usage policy, hence caching)."""
import httpx

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "AITouristGuide/1.0 (college project)"}


def geocode(query: str) -> dict | None:
    r = httpx.get(NOMINATIM, params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1},
                  headers=UA, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    x = data[0]
    return {
        "name": x.get("name") or query.title(),
        "display": x.get("display_name", query),
        "lat": float(x["lat"]),
        "lon": float(x["lon"]),
        "country_code": (x.get("address", {}).get("country_code") or "").upper(),
    }


def overpass(query: str) -> list[dict]:
    r = httpx.post(OVERPASS, data={"data": query}, headers=UA, timeout=45)
    r.raise_for_status()
    return r.json().get("elements", [])
