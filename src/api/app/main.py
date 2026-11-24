from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import ResponseCacheMiddleware
from app.core.config import get_settings
from app.core.db import database
from app.core.exceptions import register_exception_handlers
from app.routers import clubs, leaderboards, matches, players, seasons, stats, teams


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

    # La caché va por dentro de CORS (el último middleware añadido es el más externo), para que las
    # cabeceras CORS se calculen en cada petición y no se guarden con la respuesta.
    if settings.cache_entries > 0:
        app.add_middleware(ResponseCacheMiddleware, max_entries=settings.cache_entries)

    # CORS: solo los orígenes configurados (ACB_CORS_ORIGINS). Streamlit llama a la API desde el
    # servidor, no desde el navegador, así que no necesita CORS; esto es para otros clientes web.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(players.router, prefix=settings.api_prefix)
    app.include_router(teams.router, prefix=settings.api_prefix)
    app.include_router(clubs.router, prefix=settings.api_prefix)
    app.include_router(matches.router, prefix=settings.api_prefix)
    app.include_router(leaderboards.router, prefix=settings.api_prefix)
    app.include_router(seasons.router, prefix=settings.api_prefix)
    app.include_router(stats.router, prefix=settings.api_prefix)

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
