"""Pure helpers that turn OpenStreetMap tags into app categories (no network)."""
from __future__ import annotations

OUTDOOR_HISTORIC = {"castle", "fort", "monument", "memorial", "archaeological_site", "ruins"}


def osm_category(tags: dict) -> tuple[str, bool] | None:
    """Return (category, is_outdoor) or None if the element is not a sightseeing target."""
    nat, leis, hist, tour, amen = (tags.get(k) for k in ("natural", "leisure", "historic", "tourism", "amenity"))
    if nat == "beach":
        return "relax", True
    if nat in ("waterfall", "peak"):
        return "nature", True
    if leis in ("park", "garden", "nature_reserve"):
        return "nature", True
    if hist:
        return "culture", hist in OUTDOOR_HISTORIC
    if tour in ("museum", "gallery"):
        return "culture", False
    if tour == "attraction":
        return "culture", True
    if tour == "viewpoint":
        return "nature", True
    if tour == "zoo":
        return "nature", True
    if tour == "theme_park":
        return "adventure", True
    if amen == "marketplace":
        return "shopping", True
    if amen == "nightclub":
        return "nightlife", False
    return None


def osm_popularity(tags: dict) -> float:
    """OSM has no ratings. Well-documented places (wikidata/wikipedia/heritage) are usually the famous ones."""
    pop = 0.0
    if tags.get("wikidata"):
        pop += 1.0
    if tags.get("wikipedia"):
        pop += 1.0
    if tags.get("heritage") or tags.get("historic"):
        pop += 0.5
    if tags.get("tourism") == "attraction":
        pop += 0.3
    return pop


def osm_rating_proxy(tags: dict) -> float:
    return round(min(4.8, 3.6 + 0.35 * osm_popularity(tags)), 2)


def stay_tier(tags: dict) -> str:
    stars = str(tags.get("stars", "")).split(".")[0]
    if stars.isdigit():
        return "Luxury" if int(stars) >= 4 else "Mid" if int(stars) == 3 else "Budget"
    if tags.get("tourism") in ("hostel", "guest_house"):
        return "Budget"
    if tags.get("tourism") == "resort":
        return "Luxury"
    return "Mid"
