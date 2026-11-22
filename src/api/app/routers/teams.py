from __future__ import annotations

from typing import Annotated, Literal

import duckdb
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.schemas.common import CompetitionFilters, PageParams, PaginatedResponse
from app.schemas.game_highs import TeamGameHighs
from app.schemas.match import ShotEvent
from app.schemas.team import LineupCombination, TeamGameLogEntry, TeamRotations, TeamSummary, TeamTotals
from app.services import team_service

router = APIRouter(prefix="/teams", tags=["teams"])

DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
FiltersDep = Annotated[CompetitionFilters, Depends()]
PageDep = Annotated[PageParams, Depends()]


@router.get("", response_model=PaginatedResponse[TeamSummary])
def list_teams(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    q: str | None = Query(default=None, description="Búsqueda por nombre de equipo"),
):
    items, total = team_service.list_teams(cur, q, filters, page)
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset,
        has_more=page.offset + page.limit < total,
    )


@router.get("/{team_id}/totals", response_model=list[TeamTotals])
def get_team_totals(team_id: int, cur: DbDep, filters: FiltersDep):
    return team_service.get_totals(cur, team_id, filters)


@router.get("/{team_id}/games", response_model=PaginatedResponse[TeamGameLogEntry])
def get_team_games(team_id: int, cur: DbDep, filters: FiltersDep, page: PageDep):
    items, total = team_service.get_game_log(cur, team_id, filters, page)
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset,
        has_more=page.offset + page.limit < total,
    )


@router.get("/{team_id}/game-highs", response_model=TeamGameHighs)
def get_team_game_highs(team_id: int, cur: DbDep, filters: FiltersDep):
    """Mejor marca de equipo en cada estadística y el partido en el que ocurrió."""
    return team_service.get_game_highs(cur, team_id, filters)


@router.get("/{team_id}/lineups", response_model=PaginatedResponse[LineupCombination])
def get_team_lineups(
    team_id: int,
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    combination_size: int | None = Query(default=None, ge=2, le=5),
):
    items, total = team_service.get_lineup_combinations(cur, team_id, filters, combination_size, page)
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset,
        has_more=page.offset + page.limit < total,
    )


@router.get("/{team_id}/shots", response_model=list[ShotEvent])
def get_team_shots(
    team_id: int,
    cur: DbDep,
    side: Literal["own", "opponent"] = Query(default="own", description="own = tiros del equipo; opponent = tiros de sus rivales"),
    competition_phase: str | None = Query(default=None),
    clutch_only: bool = Query(default=False),
):
    """Tiros de un equipo (o de sus rivales) en su temporada, para la carta de tiro de equipo."""
    return team_service.get_shots(cur, team_id, side, competition_phase, clutch_only)


@router.get("/{team_id}/rotations", response_model=TeamRotations)
def get_team_rotations(
    team_id: int,
    cur: DbDep,
    competition_phase: str | None = Query(default=None, description="Sin fase: todas sumadas"),
):
    """
    Mapa de rotaciones de la temporada: para cada jugador y minuto de partido (0 a 39, sin
    prórrogas), % de partidos del equipo en los que estuvo en pista y segundos medios.
    Solo partidos con play-by-play.
    """
    return team_service.get_rotations(cur, team_id, competition_phase)
