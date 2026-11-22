from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.schemas.common import CompetitionFilters, PageParams, PaginatedResponse
from app.schemas.stats import PlayerStatsPer, PlayerStatsRow, TeamStatsPer, TeamStatsRow
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])

DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]
FiltersDep = Annotated[CompetitionFilters, Depends()]
PageDep = Annotated[PageParams, Depends()]


def _page(items, total, page: PageParams):
    return PaginatedResponse(
        items=items, total=total, limit=page.limit, offset=page.offset,
        has_more=page.offset + page.limit < total,
    )


@router.get("/players", response_model=PaginatedResponse[PlayerStatsRow])
def get_player_stats(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    per: PlayerStatsPer = Query(
        default="per_game",
        description="total, per_game (por defecto), per_36 o per_100 (por 100 posesiones de ataque en "
        "pista; solo partidos con play-by-play). Solo escala las columnas contables.",
    ),
    min_games: int = Query(default=0, ge=0),
):
    """
    Tabla de estadísticas de temporada: una fila por jugador, equipo, edición, competición y fase
    con todas las columnas (tiro, rebote, avanzadas, ratings). Con `team_id` es la plantilla de un
    equipo. `sort` acepta cualquier columna de `stats` (o `name`, `games`, `minutes`).
    """
    items, total = stats_service.player_stats(cur, filters, per, min_games, page)
    return _page(items, total, page)


@router.get("/teams", response_model=PaginatedResponse[TeamStatsRow])
def get_team_stats(
    cur: DbDep,
    filters: FiltersDep,
    page: PageDep,
    per: TeamStatsPer = Query(
        default="per_game",
        description="total, per_game (por defecto) o per_100 (al ritmo medio de los partidos con play-by-play).",
    ),
):
    """
    Tabla de equipos: totales propios y del rival (`opp_*`), ratings, ritmo y four factors del
    equipo y del rival. Ordenada por victorias por defecto.
    """
    items, total = stats_service.team_stats(cur, filters, per, page)
    return _page(items, total, page)
