from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import database
from app.core.exceptions import register_exception_handlers
from app.routers import clubs, leaderboards, matches, players, teams


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.connect()
    yield
    database.disconnect()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        lifespan=lifespan,
        description=(
            "API de estadísticas de la Liga ACB. Sirve el modelo analítico "
            "construido en DuckDB/dbt (staging -> intermediate -> marts) "
            "con un contrato pensado para consumo (Streamlit u otros "
            "clientes), no para exponer el warehouse tal cual."
        ),
    )

    # En desarrollo abrimos CORS a todo; en producción restringe esto al
    # origen real de tu app Streamlit.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(players.router, prefix=settings.api_prefix)
    app.include_router(teams.router, prefix=settings.api_prefix)
    app.include_router(clubs.router, prefix=settings.api_prefix)
    app.include_router(matches.router, prefix=settings.api_prefix)
    app.include_router(leaderboards.router, prefix=settings.api_prefix)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
