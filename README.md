# Wayfinder: AI-Powered Virtual Tourist Guide for Personalized Travel Planning

A responsive web app and API that builds day-wise itineraries from **live place and weather data**, grounded with
**RAG** over destination guides, with an **LLM agent** for follow-up questions.

## Architecture

```
Browser (responsive HTML/JS)
        │  REST + JWT
FastAPI ─┬─ /api/plan ──► geocode (Nominatim) ─► places (Google Places or OpenStreetMap/Overpass)
         │                └► weather (Open-Meteo) ─► planner (scoring, clustering, scheduling)
         │                └► RAG retrieve (pgvector) ─► LLM narration (Anthropic)
         ├─ /api/chat ──► LLM agent loop with tools: get_weather, find_places, search_guides
         ├─ /api/safety ─► emergency numbers + RAG passages from travel guides
         ├─ /api/auth, /api/me, /api/trips ─► users, profiles, saved / upcoming / previous trips
PostgreSQL 16 + pgvector: users, trips, kb_chunks (embeddings, HNSW index), api_cache
```

| Concern | Implementation |
|---|---|
| Generative AI / LLM | Anthropic Messages API (`LLM_MODEL`): itinerary overview and per-day tips, restricted to supplied facts |
| RAG | Wikivoyage (fallback Wikipedia) → section-aware chunks → `BAAI/bge-small-en-v1.5` embeddings (fastembed, 384-d) → pgvector cosine search |
| AI agent | Tool-use loop (max 6 steps) over live weather, live places and guide search |
| Itinerary logic | `services/planner.py`: score = rating + interest match + theme fit − weather penalties; stops are grouped by distance; travel time ≈ 28 km/h + 5 min; lunch, dinner, optional nightlife |
| Live data | Nominatim (geocoding), Overpass or Google Places (places), Open-Meteo (forecast within 16 days, else same dates last year as a seasonal estimate) |
| Recommendations | Stays and food ranked by `rating × log10(reviews)` (Google) or tag-based popularity (OSM), plus budget and diet filters |
| Persistence | Users with profile prefs, saved trips (JSON itinerary), upcoming vs previous derived from the start date |

## Run it

```bash
cp .env.example .env     # set JWT_SECRET and ANTHROPIC_API_KEY (GOOGLE_PLACES_API_KEY is optional)
docker compose up --build
# open http://localhost:8000   (API docs at /docs)
```

Local without Docker: start Postgres with the pgvector extension, set `DATABASE_URL`, then
`cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`.
The first RAG call downloads the embedding model (about 130 MB) once.

## Tests

`cd backend && pytest -q tests` covers the planner (no repeated places or meals, lunch and dinner order, weather
effect, budget ranking, nightlife rule, fewer places than days), OSM tag mapping and chunking.

## Data-source notes

- **Without a Google key** ratings and review counts do not exist: OSM has none, so place scores are *estimates*
  from tags such as `wikidata` and `heritage`. The UI says so. Add `GOOGLE_PLACES_API_KEY` (Places API New, billing
  enabled) for real ratings and review counts.
- Nominatim and Overpass are public services with usage limits; responses are cached in `api_cache`
  (geocode 30 days, places 24 h, weather 3 h). For heavy use, self-host them or use a paid provider.
- Travel times are straight-line × 1.3 at 28 km/h. A routing engine (OSRM, Google Routes) would improve them.

## Suggested evaluation (for your report)

1. **Feasibility:** share of generated days with no overlapping times and under about 10 hours; mean km per day.
2. **Relevance:** for fixed interest sets, the share of stops whose category matches an interest.
3. **Weather sensitivity:** outdoor-stop share on rainy vs dry days (the unit test shows the direction).
4. **RAG quality:** hand-label 20 queries and report top-4 retrieval hit rate.
5. **User study:** 5 to 10 users rate usefulness and trust (1 to 5) against a manually planned trip.

## Known limitations

Opening hours, ticket prices and bookings are not modelled; the LLM is told not to invent them. Up to 7 days per
trip. Weather beyond 16 days is a last-year estimate, not a forecast.
