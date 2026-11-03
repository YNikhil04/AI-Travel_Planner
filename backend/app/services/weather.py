"""Weather via Open-Meteo (free, no key). Forecast when the trip is within 16 days; otherwise the same
dates last year from the historical archive, used as a seasonal estimate."""
from datetime import date, timedelta

import httpx

FORECAST = "https://api.open-meteo.com/v1/forecast"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
WMO = {0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog",
       51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
       71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers", 81: "Rain showers",
       82: "Violent showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}


def _last_year(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year - 1, day=28)


def daily_weather(lat: float, lon: float, start: date | None, days: int) -> list[dict]:
    today = date.today()
    start = start or today
    end = start + timedelta(days=days - 1)
    try:
        if today <= start and (end - today).days <= 15:
            r = httpx.get(FORECAST, timeout=20, params={
                "latitude": lat, "longitude": lon, "timezone": "auto", "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
            r.raise_for_status()
            d = r.json()["daily"]
            return [{"date": d["time"][i], "tmax": d["temperature_2m_max"][i], "tmin": d["temperature_2m_min"][i],
                     "rain_prob": d["precipitation_probability_max"][i] or 0,
                     "summary": WMO.get(d["weather_code"][i], "Mixed"), "source": "forecast (Open-Meteo)"}
                    for i in range(len(d["time"]))]
        a, b = _last_year(start), _last_year(end)
        r = httpx.get(ARCHIVE, timeout=25, params={
            "latitude": lat, "longitude": lon, "timezone": "auto", "start_date": a.isoformat(),
            "end_date": b.isoformat(), "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"})
        r.raise_for_status()
        d = r.json()["daily"]
        out = []
        for i in range(len(d["time"])):
            mm = d["precipitation_sum"][i] or 0
            out.append({"date": (start + timedelta(days=i)).isoformat(), "tmax": d["temperature_2m_max"][i],
                        "tmin": d["temperature_2m_min"][i], "rain_prob": 70 if mm >= 2 else 20,
                        "summary": WMO.get(d["weather_code"][i], "Mixed"),
                        "source": "seasonal estimate (same dates last year, Open-Meteo archive)"})
        return out
    except Exception:
        return []
