"""
FastAPI-backend voor de (toekomstige) React-site.

Dient als tussenlaag tussen de databank (voorlopig lokaal DuckDB, later
Postgres - zie app/db.py) en de browser: React mag nooit rechtstreeks met
de databank praten, enkel via deze JSON-endpoints.

Lokaal draaien:
    uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import clubs, compare, competitions, fotmob, players, potential, signals

app = FastAPI(title="Transfermarkt Datasets API")

# Lokale ontwikkeling: Vite kiest zelf de eerste vrije poort vanaf 5173 (dus
# 5174, 5175, ... als er al iets op 5173 draait) - een vaste poort toestaan
# breekt dan ook zodra 2 dev-servers tegelijk lopen. Regex i.p.v. 1 vaste
# origin. Verstrengen naar de echte site-URL zodra die gekend is.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(clubs.router)
app.include_router(competitions.router)
app.include_router(fotmob.router)
app.include_router(potential.router)
app.include_router(compare.router)
app.include_router(signals.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
