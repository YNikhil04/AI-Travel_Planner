"""Tool-using travel agent: the LLM decides when to call live weather, live places and RAG guide search."""
import json
from datetime import date

from sqlalchemy.orm import Session

from . import places as places_svc
from .cache import cached
from .geo import geocode
from .llm import client
from .rag import ensure_kb, retrieve
from .weather import daily_weather
from ..config import settings

SYSTEM = ("You are a friendly virtual tourist guide. For weather, places or practical destination facts, call the "
          "tools instead of guessing. Say clearly when numbers are forecasts or estimates. If a tool returns "
          "nothing, say so. Keep answers short and practical.")
TOOLS = [
    {"name": "get_weather", "description": "Daily weather for a city. Forecast if within 16 days, else a seasonal "
     "estimate.", "input_schema": {"type": "object", "properties": {
         "city": {"type": "string"}, "start_date": {"type": "string", "description": "YYYY-MM-DD"},
         "days": {"type": "integer"}}, "required": ["city"]}},
    {"name": "find_places", "description": "Live nearby places for a city.", "input_schema": {
        "type": "object", "properties": {"city": {"type": "string"},
                                         "kind": {"type": "string", "enum": ["attractions", "food", "stays"]}},
        "required": ["city", "kind"]}},
    {"name": "search_guides", "description": "Search destination guide text (safety, transport, customs, "
     "sights).", "input_schema": {"type": "object", "properties": {
         "destination": {"type": "string"}, "query": {"type": "string"}}, "required": ["destination", "query"]}},
]


def _geo(db, city):
    return cached(db, f"geo:{city.lower()}", 24 * 30, lambda: geocode(city))


def run_tool(db: Session, name: str, args: dict) -> str:
    try:
        if name == "get_weather":
            g = _geo(db, args["city"])
            if not g:
                return json.dumps({"error": "city not found"})
            start = date.fromisoformat(args["start_date"]) if args.get("start_date") else None
            return json.dumps(daily_weather(g["lat"], g["lon"], start, int(args.get("days", 3))))
        if name == "find_places":
            g = _geo(db, args["city"])
            if not g:
                return json.dumps({"error": "city not found"})
            fn = {"attractions": lambda: places_svc.attractions(g["lat"], g["lon"], g["name"], ["culture", "nature"]),
                  "food": lambda: places_svc.food(g["lat"], g["lon"], g["name"], "Any"),
                  "stays": lambda: places_svc.stays(g["lat"], g["lon"], g["name"])}[args["kind"]]
            rows = cached(db, f"chat:{places_svc.provider()}:{g['lat']:.2f},{g['lon']:.2f}:{args['kind']}", 24, fn) or []
            keep = ("name", "category", "cuisine", "tier", "rating", "reviews", "address")
            return json.dumps([{k: r[k] for k in keep if k in r} for r in rows[:8]])
        if name == "search_guides":
            dest = args["destination"].lower()
            ensure_kb(db, dest, [args["destination"].title()])
            return json.dumps([{"title": c["title"], "text": c["content"][:600]}
                               for c in retrieve(db, dest, args["query"], 3)])
    except Exception as e:  # tool errors go back to the model, not to the user as a 500
        return json.dumps({"error": str(e)[:200]})
    return json.dumps({"error": "unknown tool"})


def run_agent(db: Session, message: str, history: list[dict]) -> str:
    c = client()
    if not c:
        return "The assistant needs ANTHROPIC_API_KEY to be configured on the server."
    msgs = [{"role": h["role"], "content": str(h["content"])} for h in history[-10:]
            if h.get("role") in ("user", "assistant")]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    msgs.append({"role": "user", "content": message})
    for _ in range(6):
        r = c.messages.create(model=settings.llm_model, max_tokens=1200, system=SYSTEM, tools=TOOLS, messages=msgs)
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text") or "I have no answer for that."
        msgs.append({"role": "assistant", "content": r.content})
        msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": b.id, "content": run_tool(db, b.name, b.input)}
            for b in r.content if b.type == "tool_use"]})
    return "I could not finish that. Please try a narrower question."
