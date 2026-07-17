from fastapi import FastAPI
from src.api.app.routers.players import router as players_router
from src.api.app.routers.teams import router as teams_router

app = FastAPI(
    title="ACB Statistics API",
    version="1.0.0"
)

app.include_router(players_router)
app.include_router(teams_router)