from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import ChatIn
from ..services.agent import run_agent
from ..services.cache import cached
from ..services.geo import geocode
from ..services.rag import ensure_kb, retrieve

router = APIRouter(prefix="/api", tags=["misc"])

EMERGENCY = {
    "IN": [["112", "All emergencies"], ["100", "Police"], ["108", "Ambulance"], ["101", "Fire"],
           ["1363", "Tourist helpline"], ["1091", "Women helpline"]],
    "US": [["911", "All emergencies"]], "GB": [["999", "All emergencies"], ["112", "All emergencies"]],
    "AU": [["000", "All emergencies"]], "DEFAULT": [["112", "Emergency number used in the EU and many countries"]],
}


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/safety")
def safety(destination: str, db: Session = Depends(get_db)):
    geo = cached(db, f"geo:{destination.lower()}", 24 * 30, lambda: geocode(destination))
    if not geo:
        raise HTTPException(404, "Destination not found")
    key, passages = geo["name"].lower(), []
    try:
        ensure_kb(db, key, [geo["name"], destination.title()])
        passages = retrieve(db, key, "stay safe scams crime health water emergency police hospital", 4)
    except Exception:
        db.rollback()
    return {"destination": geo["name"], "country_code": geo["country_code"],
            "numbers": EMERGENCY.get(geo["country_code"], EMERGENCY["DEFAULT"]),
            "guide_passages": [{"title": p["title"], "text": p["content"], "source": p["source"]} for p in passages]}


@router.post("/chat")
def chat(body: ChatIn, db: Session = Depends(get_db)):
    return {"reply": run_agent(db, body.message, body.history)}
