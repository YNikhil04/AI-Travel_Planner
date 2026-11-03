from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user, hash_password, make_token, verify_password
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, RegisterIn

router = APIRouter(prefix="/api", tags=["auth"])


def _out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "prefs": u.prefs}


@router.post("/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    u = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), prefs={})
    db.add(u)
    db.commit()
    return {"token": make_token(u.id), "user": _out(u)}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(u.id), "user": _out(u)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _out(user)


@router.put("/me/prefs")
def set_prefs(prefs: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.prefs = {k: prefs[k] for k in ("interests", "theme", "budget", "diet") if k in prefs}
    db.commit()
    return _out(user)
