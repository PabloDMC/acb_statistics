from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.schemas.common import CompetitionFilters, PageParams, PaginatedResponse
from app.schemas.match import LineupStint, MatchSummary, ShotEvent
from app.services import match_service

router = APIRouter(prefix="/matches", tags=["matches"])

DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
FiltersDep = Annotated[CompetitionFilters, Depends()]
PageDep = Annotated[PageParams, Depends()]


@router.get("", response_model=PaginatedResponse[MatchSummary])
def list_matches(cur: DbDep, filters: FiltersDep, page: PageDep):
    items, total = match_service.list_matches(cur, filters, page)
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset,
        has_more=page.offset + page.limit < total,
    )


@router.get("/{match_id}", response_model=MatchSummary)
def get_match(match_id: int, cur: DbDep):
    return match_service.get_match(cur, match_id)


@router.get("/{match_id}/shots", response_model=list[ShotEvent])
def get_match_shots(
    match_id: int,
    cur: DbDep,
    team_id: int | None = Query(default=None),
    player_id: int | None = Query(default=None),
    clutch_only: bool = Query(default=False, description="Solo lanzamientos marcados como clutch"),
):
    """
    Datos ligeros pensados para pintar un shot chart (punto 33 del resumen):
    un evento por lanzamiento, sin agregar.
    """
    return match_service.get_shots(cur, match_id, team_id, player_id, clutch_only)


@router.get("/{match_id}/lineups", response_model=list[LineupStint])
def get_match_lineups(match_id: int, cur: DbDep):
    return match_service.get_lineup_stints(cur, match_id)
