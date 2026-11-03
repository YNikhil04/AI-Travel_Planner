from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Interest = Literal["culture", "nature", "adventure", "relax", "shopping", "nightlife"]


class PlanRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=120)
    start_date: date | None = None
    days: int = Field(3, ge=1, le=7)
    theme: Literal["Relaxed", "Adventure", "Cultural", "Family", "Romantic"] = "Relaxed"
    interests: list[Interest] = ["culture", "nature"]
    budget: Literal["Budget", "Mid", "Luxury"] = "Mid"
    diet: Literal["Any", "Veg"] = "Any"


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: str
    password: str


class SaveTripIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    plan: dict


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = []
