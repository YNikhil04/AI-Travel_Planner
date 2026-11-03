"""LLM layer (Anthropic). Everything degrades gracefully when no API key is configured."""
import json
import re

from ..config import settings


def client():
    if not settings.anthropic_api_key:
        return None
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _compact(itin: dict) -> list[dict]:
    days = []
    for d in itin["days"]:
        days.append({"day": d["day"], "weather": f"{d['weather'].get('summary')}, rain chance "
                     f"{d['weather'].get('rain_prob')}%, max {d['weather'].get('tmax')}C",
                     "plan": [f"{i['start']} {i.get('label', 'Visit')}: {i['place']['name']}" for i in d["items"]]})
    return days


def fallback_summary(dest: str, req: dict, itin: dict) -> dict:
    n = sum(1 for d in itin["days"] for i in d["items"] if i["type"] == "stop")
    return {"summary": f"{len(itin['days'])}-day {req['theme'].lower()} plan for {dest} with {n} stops, "
                       f"about {itin['total_km']:.0f} km of travel. Add an Anthropic API key for a written overview.",
            "day_tips": [], "llm": False}


def narrate(dest: str, req: dict, itin: dict, context: list[dict]) -> dict:
    c = client()
    if not c:
        return fallback_summary(dest, req, itin)
    system = ("You are a careful travel writer. Use ONLY the itinerary and guide excerpts provided. Do not invent "
              "opening hours, prices or facts. Reply with a single JSON object: "
              '{"summary": "2-3 sentence overview", "day_tips": ["one practical tip per day, in order"]}')
    user = json.dumps({"destination": dest, "theme": req["theme"], "interests": req["interests"],
                       "itinerary": _compact(itin), "guide_excerpts": [x["content"][:500] for x in context[:4]]})
    try:
        r = c.messages.create(model=settings.llm_model, max_tokens=700, system=system,
                              messages=[{"role": "user", "content": user}])
        text = "".join(b.text for b in r.content if b.type == "text")
        data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        return {"summary": str(data.get("summary", "")), "day_tips": [str(x) for x in data.get("day_tips", [])],
                "llm": True}
    except Exception:
        return fallback_summary(dest, req, itin)
