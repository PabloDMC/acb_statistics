from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.schemas.club import ClubTeamHistoryEntry
from app.services import club_service

router = APIRouter(prefix="/clubs", tags=["clubs"])

DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


@router.get("/{club_id}/teams", response_model=list[ClubTeamHistoryEntry])
def get_club_team_history(club_id: int, cur: DbDep):
    """
    Trayectoria histórica de un club: qué team_id tuvo en cada
    edición/competición. Útil para resolver "dame la plantilla del Breogán
    en 2022-23" sin tener que conocer de antemano el team_id de esa temporada:
    primero llamas aquí, luego usas ese team_id (o directamente club_id como
    filtro) en /teams/{team_id}/... o en los filtros club_id de otros endpoints.
    """
    return club_service.get_team_history(cur, club_id)
