from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Trip, User
from ..schemas import SaveTripIn

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _row(t: Trip) -> dict:
    end = t.start_date + timedelta(days=t.days - 1) if t.start_date else None
    return {"id": t.id, "title": t.title, "destination": t.destination, "start_date": t.start_date, "days": t.days,
            "theme": t.theme, "status": "past" if end and end < date.today() else "upcoming"}


@router.post("")
def save_trip(body: SaveTripIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = body.plan.get("request") or {}
    try:
        t = Trip(user_id=user.id, title=body.title, destination=body.plan["destination"]["name"],
                 start_date=date.fromisoformat(r["start_date"]) if r.get("start_date") else None,
                 days=int(r["days"]), theme=r["theme"], budget=r["budget"], diet=r["diet"],
                 interests=r.get("interests", []), itinerary=body.plan)
    except (KeyError, ValueError, TypeError):
        raise HTTPException(422, "Plan is missing required fields")
    db.add(t)
    db.commit()
    return _row(t)


@router.get("")
def list_trips(scope: str = "all", user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = [_row(t) for t in db.scalars(select(Trip).where(Trip.user_id == user.id).order_by(Trip.id.desc()))]
    return rows if scope == "all" else [r for r in rows if r["status"] == scope]


def _own(db: Session, user: User, trip_id: int) -> Trip:
    t = db.get(Trip, trip_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Trip not found")
    return t


@router.get("/{trip_id}")
def get_trip(trip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _own(db, user, trip_id).itinerary


@router.delete("/{trip_id}")
def delete_trip(trip_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, user, trip_id))
    db.commit()
    return {"deleted": trip_id}
