from __future__ import annotations

from typing import Annotated, Literal

import duckdb
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.leaderboard import (
    PLAYER_COUNTABLE_METRICS,
    PLAYER_LEADERBOARD_METRICS,
    TEAM_COUNTABLE_METRICS,
    TEAM_LEADERBOARD_METRICS,
    LeaderboardPer,
    LeaderboardScope,
    PlayerLeaderboardEntry,
    PlayerMetric,
    ShootingLeaderboardEntry,
    ShootingMetric,
    TeamLeaderboardEntry,
    TeamMetric,
)
from app.schemas.records import (
    AssistKind,
    AssistPairEntry,
    ClutchLeaderboardEntry,
    ClutchMetric,
    GameRecordEntry,
    GameRecordMetric,
    TeamGameRecordMetric,
)
from app.services import leaderboard_service, records_service

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
    metric: PlayerMetric = Query(..., description="Métrica por la que ordenar"),
    min_games: int = Query(default=1, ge=0, description="Filtra jugadores con pocos partidos jugados"),
    min_minutes: float = Query(default=0, ge=0, description="Mínimo de minutos por partido jugado"),
    scope: LeaderboardScope = Query(
        default="season",
        description="'season': mejores marcas por temporada/fase (si no filtras edition_id, es histórico). 'career': agregado de toda la carrera dentro de los filtros dados.",
    ),
    per: LeaderboardPer = Query(
        default="total",
        description="'total' (por defecto), 'per_game', 'per_100_poss' o 'per_40_min'. Solo aplica a métricas contables (points, assists, rebounds, steals, blocks, rating).",
    ),
):
    return leaderboard_service.player_leaderboard(cur, metric.value, filters, page, min_games, scope, per, min_minutes)


@router.get("/teams", response_model=list[TeamLeaderboardEntry])
def get_team_leaderboard(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    metric: TeamMetric = Query(..., description="Métrica por la que ordenar"),
    scope: LeaderboardScope = Query(default="season", description="'season' o 'career' (agregado por club de toda su trayectoria dentro de los filtros dados)."),
    per: LeaderboardPer = Query(default="total", description="'total', 'per_game', 'per_100_poss' o 'per_40_min'. Solo aplica a métricas contables."),
):
    return leaderboard_service.team_leaderboard(cur, metric.value, filters, page, scope, per)


@router.get("/shooting", response_model=list[ShootingLeaderboardEntry])
def get_shooting_leaderboard(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    metric: ShootingMetric = Query(..., description="made, attempted, pct o frequency"),
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
    return leaderboard_service.shooting_leaderboard(cur, metric.value, zone, clutch_only, filters, min_attempts, page)


@router.get("/shooting/zones")
def get_available_shot_zones(cur: DbDep):
    """Valores reales de zona en tu warehouse, para montar un selector sin hardcodearlos."""
    return {"zones": leaderboard_service.available_shot_zones(cur)}


@router.get("/clutch", response_model=list[ClutchLeaderboardEntry])
def get_clutch_leaderboard(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    metric: ClutchMetric = Query(default="points"),
    min_attempts: int = Query(default=10, ge=0, description="Mínimo de intentos para los porcentajes"),
):
    """
    Líderes en clutch (últimos 5 minutos del último cuarto y prórrogas con ±5 puntos), siempre en
    TOTALES. Sin edition_id es el histórico de la liga; con edition_id, la temporada; con
    team_id/club_id, el equipo. Solo partidos con jugada a jugada.
    """
    return records_service.clutch_leaderboard(cur, metric, filters, min_attempts, page)


@router.get("/game-records", response_model=list[GameRecordEntry])
def get_game_records(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    target: Literal["players", "teams"] = Query(default="players"),
    metric: str = Query(default="points", description="Ver GameRecordMetric (jugadores) o TeamGameRecordMetric (equipos)"),
):
    """
    Mejores partidos individuales (o de equipo) en una estadística: récords históricos, de una
    temporada o de un equipo según los filtros. Incluye rival, fecha y resultado.
    """
    allowed = TeamGameRecordMetric.__args__ if target == "teams" else GameRecordMetric.__args__
    if metric not in allowed:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=f"metric debe ser una de: {list(allowed)}")
    return records_service.game_records(cur, target, metric, filters, page)


@router.get("/assist-pairs", response_model=list[AssistPairEntry])
def get_assist_pairs(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    kind: AssistKind = Query(default="all", description="all, 2P, 3P o FT (asistencias que acaban en tiros libres)"),
    sort: Literal["plays", "points"] = Query(default="plays", description="Por canastas asistidas o por puntos"),
):
    """
    Parejas asistente -> anotador más prolíficas, en totales, con el desglose por tipo de canasta.
    Solo partidos con jugada a jugada.
    """
    return records_service.assist_pairs(cur, filters, kind, sort, page)
