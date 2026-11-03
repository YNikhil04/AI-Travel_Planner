"""Deterministic, weather-aware itinerary planner. Pure Python: no network, no database."""
from __future__ import annotations

import math

THEME_CATS = {
    "Relaxed": ["relax", "nature"],
    "Adventure": ["adventure", "nature"],
    "Cultural": ["culture", "shopping"],
    "Family": ["nature", "culture", "relax"],
    "Romantic": ["relax", "nature", "nightlife"],
}
VISIT_HOURS = {"culture": 1.5, "nature": 2.0, "adventure": 3.0, "relax": 1.5, "shopping": 1.5, "nightlife": 2.0}
NEUTRAL = {"rain_prob": 0, "tmax": None, "tmin": None, "summary": "No weather data", "source": "unavailable"}
CITY_SPEED_KMH = 28.0


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def road_km(a: dict, b: dict) -> float:
    """Straight-line distance x1.3 as a stand-in for road distance."""
    return haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) * 1.3


def travel_minutes(km: float) -> int:
    return round(km / CITY_SPEED_KMH * 60 + 5)


def clock(t: float) -> str:
    h, m = int(t), round((t - int(t)) * 60)
    if m == 60:
        h, m = h + 1, 0
    return f"{(h % 12) or 12}:{m:02d} {'PM' if h % 24 >= 12 else 'AM'}"


def day_score(p: dict, interests: list[str], theme: str, w: dict) -> tuple[float, list[str]]:
    s = float(p.get("rating") or 4.0)
    why: list[str] = []
    cat = p["category"]
    if cat in interests:
        s += 3
        why.append(f"matches your interest in {cat}")
    if cat in THEME_CATS.get(theme, []):
        s += 2
        why.append(f"fits a {theme.lower()} trip")
    rainy = (w.get("rain_prob") or 0) >= 60
    hot = (w.get("tmax") or 0) >= 36
    if p.get("outdoor") and rainy:
        s -= 3
        why.append("outdoor stop on a day that is likely to be rainy")
    if p.get("outdoor") and hot and VISIT_HOURS.get(cat, 1.5) >= 2:
        s -= 1
        why.append("long outdoor stay in strong heat")
    if p.get("reviews") and (p.get("rating") or 0) >= 4.5:
        why.append(f"rated {p['rating']} from {p['reviews']:,} reviews")
    return s, why


def _pick_meal(foods: list[dict], near: dict, used: set) -> dict | None:
    pool = [f for f in foods if f["id"] not in used] or foods
    if not pool:
        return None
    return min(pool, key=lambda f: -f["score"] + road_km(near, f) / 2)


def plan_trip(places, foods, stays, weather, *, interests, theme, days, budget, diet="Any") -> dict:
    per = 3 if theme in ("Relaxed", "Romantic") else 4
    want_night = "nightlife" in interests or theme == "Romantic"
    foods = [f for f in foods if diet == "Any" or f.get("veg")] or foods
    remaining = list(places)
    used_food: set = set()
    out_days, total_km = [], 0.0

    for i in range(days):
        w = weather[i] if i < len(weather) else NEUTRAL
        scored = sorted(
            ({"s": s, "why": why, "p": p} for p in remaining if p["category"] != "nightlife"
             for s, why in [day_score(p, interests, theme, w)]),
            key=lambda x: -x["s"],
        )
        if not scored:
            break
        stops = [scored.pop(0)]
        pool = scored[: per * 4]
        while len(stops) < per and pool:
            last = stops[-1]["p"]
            # relevance first, with a mild penalty (0.15 points/km) so each day stays geographically compact
            j = max(range(len(pool)), key=lambda k: pool[k]["s"] - 0.15 * road_km(last, pool[k]["p"]))
            stops.append(pool.pop(j))

        t, prev, lunch_done, day_km, hours = 9.0, None, False, 0.0, 0.0
        items: list[dict] = []
        done_ids = set()
        for st in stops:
            p, leg = st["p"], None
            if prev:
                k = road_km(prev, p)
                leg = {"km": round(k, 1), "min": travel_minutes(k)}
                t += leg["min"] / 60
                day_km += k
            if not lunch_done and t >= 12.5:
                m = _pick_meal(foods, prev or p, used_food)
                if m:
                    used_food.add(m["id"])
                    items.append({"type": "meal", "label": "Lunch", "start": clock(t), "place": m})
                t += 1.0
                lunch_done = True
            dur = VISIT_HOURS.get(p["category"], 1.5)
            if items and t + dur > 19.0:
                break
            items.append({"type": "stop", "start": clock(t), "end": clock(t + dur), "place": p,
                          "why": st["why"], "leg": leg})
            done_ids.add(p["id"])
            hours += dur
            t += dur
            prev = p
        if not lunch_done and prev:
            t = max(t, 12.5)
            m = _pick_meal(foods, prev, used_food)
            if m:
                used_food.add(m["id"])
                items.append({"type": "meal", "label": "Lunch", "start": clock(t), "place": m})
            t += 1.0
        t = max(t + 0.5, 19.0)
        dm = _pick_meal(foods, prev, used_food) if prev else None
        if dm:
            used_food.add(dm["id"])
            items.append({"type": "meal", "label": "Dinner", "start": clock(t), "place": dm})
            t += 1.25
        if want_night and prev:
            nights = [p for p in remaining if p["category"] == "nightlife"]
            if nights:
                best = max(nights, key=lambda p: day_score(p, interests, theme, w)[0])
                k = road_km(dm or prev, best)
                t = max(t + travel_minutes(k) / 60, 20.5)
                items.append({"type": "stop", "start": clock(t), "end": clock(t + 2), "place": best,
                              "why": ["evening option after dinner"],
                              "leg": {"km": round(k, 1), "min": travel_minutes(k)}})
                done_ids.add(best["id"])
                day_km += k
        remaining = [p for p in remaining if p["id"] not in done_ids]
        total_km += day_km
        out_days.append({"day": i + 1, "weather": w, "items": items,
                         "km": round(day_km, 1), "hours": round(hours, 1)})

    ranked_stays = sorted(stays, key=lambda s: -(s["score"] + (3 if s["tier"] == budget else 0)))
    return {
        "days": out_days,
        "stays": ranked_stays[:5],
        "foods": sorted(foods, key=lambda f: -f["score"])[:6],
        "total_km": round(total_km, 1),
        "requested_days": days,
    }
