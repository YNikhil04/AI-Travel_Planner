import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.chunking import chunk_text  # noqa: E402
from app.services.osm_tags import osm_category, stay_tier  # noqa: E402
from app.services.planner import clock, haversine_km, plan_trip  # noqa: E402


def P(i, cat, lat, lon, outdoor, rating=4.2):
    return {"id": f"p{i}", "name": f"Place {i}", "category": cat, "lat": lat, "lon": lon, "outdoor": outdoor,
            "rating": rating, "reviews": 100}


def F(i, lat, lon, score=4.0, veg=True):
    return {"id": f"f{i}", "name": f"Food {i}", "lat": lat, "lon": lon, "score": score, "veg": veg,
            "cuisine": "x", "price": "Mid"}


PLACES = [P(i, c, 17.36 + i * 0.01, 78.47 + i * 0.01, o) for i, (c, o) in enumerate(
    [("culture", False), ("culture", True), ("nature", True), ("relax", True), ("shopping", True),
     ("adventure", True), ("culture", False), ("nature", True), ("nightlife", False)])]
FOODS = [F(i, 17.37 + i * 0.01, 78.48) for i in range(6)]
STAYS = [{"id": "s1", "name": "A", "tier": "Budget", "score": 3.5}, {"id": "s2", "name": "B", "tier": "Luxury", "score": 4.0}]
DRY = [{"rain_prob": 5, "tmax": 30, "summary": "Clear sky", "source": "t"}] * 3
WET = [{"rain_prob": 90, "tmax": 25, "summary": "Rain", "source": "t"}] * 3


def run(weather=DRY, **kw):
    args = dict(interests=["culture"], theme="Cultural", days=3, budget="Luxury")
    args.update(kw)
    return plan_trip(PLACES, FOODS, STAYS, weather, **args)


def test_haversine_one_degree_longitude_at_equator():
    assert abs(haversine_km(0, 0, 0, 1) - 111.19) < 0.5


def test_clock_format():
    assert clock(9.0) == "9:00 AM" and clock(13.5) == "1:30 PM" and clock(0.25) == "12:15 AM"


def test_no_place_or_meal_repeats_across_days():
    plan = run()
    stops = [i["place"]["id"] for d in plan["days"] for i in d["items"] if i["type"] == "stop"]
    meals = [i["place"]["id"] for d in plan["days"] for i in d["items"] if i["type"] == "meal"]
    assert len(stops) == len(set(stops)) and len(meals) == len(set(meals))


def test_every_day_has_lunch_and_dinner_in_order():
    for d in run()["days"]:
        labels = [i["label"] for i in d["items"] if i["type"] == "meal"]
        assert labels[0] == "Lunch" and labels[-1] == "Dinner"


def test_rain_pushes_outdoor_stops_down():
    kw = dict(interests=["nature"], theme="Relaxed", days=1)
    dry_out = sum(i["place"]["outdoor"] for d in run(DRY, **kw)["days"] for i in d["items"] if i["type"] == "stop")
    wet_out = sum(i["place"]["outdoor"] for d in run(WET, **kw)["days"] for i in d["items"] if i["type"] == "stop")
    assert wet_out < dry_out


def test_budget_tier_ranks_first():
    assert run(budget="Budget")["stays"][0]["tier"] == "Budget"
    assert run(budget="Luxury")["stays"][0]["tier"] == "Luxury"


def test_nightlife_only_when_wanted():
    has = lambda p: any(i["type"] == "stop" and i["place"]["category"] == "nightlife" for d in p["days"] for i in d["items"])
    assert not has(run(interests=["culture"], theme="Cultural"))
    assert has(run(interests=["nightlife"], theme="Romantic"))


def test_fewer_places_than_days_does_not_crash():
    plan = plan_trip(PLACES[:2], FOODS, STAYS, DRY, interests=["culture"], theme="Cultural", days=7, budget="Mid")
    assert 1 <= len(plan["days"]) <= 7


def test_osm_category_and_tiers():
    assert osm_category({"natural": "beach"}) == ("relax", True)
    assert osm_category({"historic": "fort"}) == ("culture", True)
    assert osm_category({"tourism": "museum"}) == ("culture", False)
    assert osm_category({"shop": "bakery"}) is None
    assert stay_tier({"stars": "5"}) == "Luxury" and stay_tier({"tourism": "hostel"}) == "Budget"


def test_chunking_splits_and_skips_references():
    text = "== See ==\n" + ("Old fort with a long history. " * 60) + "\n== References ==\nignore me ignore me ignore me ignore me ignore me ignore me ignore"
    chunks = chunk_text(text)
    assert len(chunks) >= 2 and all(t == "See" for t, _ in chunks) and all(len(c) <= 1000 for _, c in chunks)
