from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.schemas.common import CompetitionFilters, PageParams, PaginatedResponse
from app.schemas.game_highs import PlayerGameHighs
from app.schemas.match import ShotEvent
from app.schemas.player import (
    PlayerBasicInfo,
    PlayerGameLogEntry,
    PlayerImpact,
    PlayerLineupParticipation,
    PlayerProfile,
    PlayerShootingProfile,
    PlayerSummary,
    PlayerTotals,
)
from app.services import player_service

router = APIRouter(prefix="/players", tags=["players"])

DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
FiltersDep = Annotated[CompetitionFilters, Depends()]
PageDep = Annotated[PageParams, Depends()]


@router.get("", response_model=PaginatedResponse[PlayerSummary])
def list_players(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    q: str | None = Query(default=None, description="Búsqueda por nombre"),
):
    items, total = player_service.list_players(cur, q, filters, page)
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset,
        has_more=page.offset + page.limit < total,
    )


@router.get("/{player_id}", response_model=PlayerBasicInfo)
def get_player(player_id: int, cur: DbDep):
    return player_service.get_basic_info(cur, player_id)


@router.get("/{player_id}/profile", response_model=PlayerProfile)
def get_player_profile(player_id: int, cur: DbDep, filters: FiltersDep):
    """
    Endpoint pensado para pintar de una sola llamada la página de jugador
    estilo Basketball-Reference (perfil + producción + eficiencia + impacto
    + shooting). Ver punto 32 del resumen del proyecto.
    """
    return player_service.get_profile(cur, player_id, filters)


@router.get("/{player_id}/totals", response_model=list[PlayerTotals])
def get_player_totals(player_id: int, cur: DbDep, filters: FiltersDep):
    return player_service.get_totals(cur, player_id, filters)


@router.get("/{player_id}/games", response_model=PaginatedResponse[PlayerGameLogEntry])
def get_player_games(player_id: int, cur: DbDep, filters: FiltersDep, page: PageDep):
    items, total = player_service.get_game_log(cur, player_id, filters, page)
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset,
        has_more=page.offset + page.limit < total,
    )


@router.get("/{player_id}/shooting", response_model=list[PlayerShootingProfile])
def get_player_shooting(player_id: int, cur: DbDep, filters: FiltersDep):
    return player_service.get_shooting_profile(cur, player_id, filters)


@router.get("/{player_id}/impact", response_model=list[PlayerImpact])
def get_player_impact(player_id: int, cur: DbDep, filters: FiltersDep):
    return player_service.get_impact(cur, player_id, filters)


@router.get("/{player_id}/shots", response_model=list[ShotEvent])
def get_player_shots(
    player_id: int,
    cur: DbDep,
    filters: FiltersDep,
    clutch_only: bool = Query(default=False, description="Solo lanzamientos marcados como clutch"),
):
    """
    Lanzamientos de temporada completa (no agregados), pensados para un shot
    chart de jugador. Para un único partido, usa /matches/{match_id}/shots.
    """
    return player_service.get_shots(cur, player_id, filters, clutch_only)


@router.get("/{player_id}/game-highs", response_model=PlayerGameHighs)
def get_player_game_highs(player_id: int, cur: DbDep, filters: FiltersDep):
    """Mejor marca de cada estadística y el partido en el que ocurrió."""
    return player_service.get_game_highs(cur, player_id, filters)


@router.get("/{player_id}/lineups", response_model=list[PlayerLineupParticipation])
def get_player_lineups(
    player_id: int,
    cur: DbDep,
    filters: FiltersDep,
    limit: int = Query(default=10, ge=1, le=100),
):
    return player_service.get_lineup_participations(cur, player_id, filters, limit)
