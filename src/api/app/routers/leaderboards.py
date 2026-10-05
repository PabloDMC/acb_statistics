from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.leaderboard import (
    PLAYER_COUNTABLE_METRICS,
    PLAYER_LEADERBOARD_METRICS,
    SHOOTING_LEADERBOARD_METRICS,
    TEAM_COUNTABLE_METRICS,
    TEAM_LEADERBOARD_METRICS,
    PlayerLeaderboardEntry,
    ShootingLeaderboardEntry,
    TeamLeaderboardEntry,
)
from app.services import leaderboard_service

router = APIRouter(prefix="/leaderboards", tags=["leaderboards"])

DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
FiltersDep = Annotated[CompetitionFilters, Depends()]
PageDep = Annotated[PageParams, Depends()]


@router.get("/metrics")
def list_available_metrics():
    """Métricas soportadas, para que Streamlit pueda montar un selector sin hardcodearlas."""
    return {
        "players": sorted(PLAYER_LEADERBOARD_METRICS),
        "players_countable": sorted(PLAYER_COUNTABLE_METRICS),  # admiten per_game/per_100_poss/per_40_min
        "teams": sorted(TEAM_LEADERBOARD_METRICS),
        "teams_countable": sorted(TEAM_COUNTABLE_METRICS),
        "scopes": ["season", "career"],
        "per_options": ["total", "per_game", "per_100_poss", "per_40_min"],
    }


@router.get("/players", response_model=list[PlayerLeaderboardEntry])
def get_player_leaderboard(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    metric: str = Query(..., description=f"Una de: {sorted(PLAYER_LEADERBOARD_METRICS)}"),
    min_games: int = Query(default=1, ge=0, description="Filtra jugadores con pocos partidos jugados"),
    scope: str = Query(
        default="season",
        description="'season': mejores marcas por temporada/fase (si no filtras edition_id, es histórico). 'career': agregado de toda la carrera dentro de los filtros dados.",
    ),
    per: str = Query(
        default="total",
        description="'total' (por defecto), 'per_game', 'per_100_poss' o 'per_40_min'. Solo aplica a métricas contables (points, assists, rebounds, steals, blocks, rating).",
    ),
):
    return leaderboard_service.player_leaderboard(cur, metric, filters, page, min_games, scope, per)


@router.get("/teams", response_model=list[TeamLeaderboardEntry])
def get_team_leaderboard(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    metric: str = Query(..., description=f"Una de: {sorted(TEAM_LEADERBOARD_METRICS)}"),
    scope: str = Query(default="season", description="'season' o 'career' (agregado de toda la trayectoria del equipo dentro de los filtros dados)."),
    per: str = Query(default="total", description="'total', 'per_game' o 'per_100_poss'. Solo aplica a 'points'."),
):
    return leaderboard_service.team_leaderboard(cur, metric, filters, page, scope, per)


@router.get("/shooting", response_model=list[ShootingLeaderboardEntry])
def get_shooting_leaderboard(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    metric: str = Query(..., description=f"Una de: {sorted(SHOOTING_LEADERBOARD_METRICS)}"),
    zone: str | None = Query(
        default=None,
        description="Zona exacta (ver GET /leaderboards/shooting/zones). Si se omite, combina todas las zonas.",
    ),
    clutch_only: bool = Query(
        default=False,
        description="Si es true, solo cuenta lanzamientos marcados como clutch en fact_shots.is_clutch.",
    ),
    min_attempts: int = Query(default=10, ge=0, description="Filtra muestras pequeñas"),
):
    """
    Leaderboard de tiro por zona y/o en clutch (punto 4 de tu lista:
    clutch solo está materializado hoy a nivel de lanzamiento individual en
    fact_shots.is_clutch, así que esto es lo que se puede ofrecer de forma
    fiable sin tocar dbt).
    """
    return leaderboard_service.shooting_leaderboard(cur, metric, zone, clutch_only, filters, min_attempts, page)


@router.get("/shooting/zones")
def get_available_shot_zones(cur: DbDep):
    """Valores reales de zona en tu warehouse, para montar un selector sin hardcodearlos."""
    return {"zones": leaderboard_service.available_shot_zones(cur)}
