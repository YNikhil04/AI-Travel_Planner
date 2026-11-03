from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import PlanRequest
from ..services import llm, places as P
from ..services.cache import cached
from ..services.geo import geocode
from ..services.planner import plan_trip
from ..services.rag import ensure_kb, retrieve
from ..services.weather import daily_weather

router = APIRouter(prefix="/api", tags=["plan"])


@router.post("/plan")
def create_plan(req: PlanRequest, db: Session = Depends(get_db)):
    geo = cached(db, f"geo:{req.destination.lower()}", 24 * 30, lambda: geocode(req.destination))
    if not geo:
        raise HTTPException(404, "Destination not found. Try a city or region name.")
    lat, lon, city, prov = geo["lat"], geo["lon"], geo["name"], P.provider()
    pos = f"{lat:.2f},{lon:.2f}"

    weather = cached(db, f"wx:{pos}:{req.start_date}:{req.days}", 3,
                     lambda: daily_weather(lat, lon, req.start_date, req.days) or None) or []
    places = cached(db, f"att:{prov}:{pos}:{','.join(sorted(req.interests))}", 24,
                    lambda: P.attractions(lat, lon, city, req.interests)) or []
    foods = cached(db, f"food:{prov}:{pos}:{req.diet}", 24, lambda: P.food(lat, lon, city, req.diet)) or []
    stays = cached(db, f"stay:{prov}:{pos}", 24, lambda: P.stays(lat, lon, city)) or []
    if not places:
        raise HTTPException(502, "No places were found for this destination from the data provider.")

    itin = plan_trip(places, foods, stays, weather, interests=req.interests, theme=req.theme, days=req.days,
                     budget=req.budget, diet=req.diet)

    kb_key, context = city.lower(), []
    try:
        ensure_kb(db, kb_key, [city, req.destination.title()])
        context = retrieve(db, kb_key, f"{req.theme} trip: {' '.join(req.interests)} things to do in {city}", 4)
    except Exception:
        db.rollback()  # RAG is an enhancement; the plan is still valid without it
    text = llm.narrate(city, req.model_dump(mode="json"), itin, context)

    return {
        "destination": {"name": city, "display": geo["display"], "lat": lat, "lon": lon,
                        "country_code": geo["country_code"]},
        "request": req.model_dump(mode="json"),
        "itinerary": itin,
        "summary": text["summary"],
        "day_tips": text["day_tips"],
        "sources": {"places": prov, "weather": weather[0]["source"] if weather else "unavailable",
                    "llm": text["llm"],
                    "guide_passages": [{"title": c["title"], "source": c["source"], "similarity": c["similarity"]}
                                       for c in context]},
    }
