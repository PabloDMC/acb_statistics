from __future__ import annotations

from typing import Annotated

import duckdb
from fastapi import APIRouter, Depends, Query

from app.core.db import get_db
from app.schemas.season import EditionInfo, LeagueZone, SearchResults, Standings, StandingsHistory
from app.services import season_service

router = APIRouter(tags=["seasons"])

DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


@router.get("/editions", response_model=list[EditionInfo])
def list_editions(cur: DbDep):
    """Temporadas disponibles con sus competiciones y fases (para los selectores), de la más reciente a la más antigua."""
    return season_service.list_editions(cur)


@router.get("/standings", response_model=Standings)
def get_standings(
    cur: DbDep,
    edition_id: int = Query(description="Temporada (ver /editions)"),
    competition_id: int = Query(default=1, description="1 = Liga Endesa"),
    competition_phase: str = Query(default="LR", description="Fase: LR (liga regular) por defecto"),
    round: int | None = Query(default=None, ge=1, description="Clasificación tras esta jornada"),
):
    """
    Clasificación con el desempate oficial de la ACB: victorias; entre empatados, enfrentamientos
    directos, basket-average particular, basket-average general y puntos a favor.
    """
    return season_service.get_standings(cur, edition_id, competition_id, competition_phase, round)


@router.get("/standings/history", response_model=StandingsHistory)
def get_standings_history(
    cur: DbDep,
    edition_id: int = Query(description="Temporada (ver /editions)"),
    competition_id: int = Query(default=1),
    competition_phase: str = Query(default="LR"),
):
    """Posición de cada equipo tras cada jornada, para el gráfico de evolución de la clasificación."""
    return season_service.get_standings_history(cur, edition_id, competition_id, competition_phase)


@router.get("/league/shot-zones", response_model=list[LeagueZone])
def get_league_shot_zones(
    cur: DbDep,
    edition_id: int | None = Query(default=None, description="Sin edición: todas las temporadas"),
):
    """Tiro de toda la liga por zona: la referencia para colorear cartas de tiro frente a la media."""
    return season_service.league_shot_zones(cur, edition_id)


@router.get("/search", response_model=SearchResults)
def search(
    cur: DbDep,
    q: str = Query(min_length=2, description="Texto a buscar (sin distinguir mayúsculas ni acentos)"),
    limit: int = Query(default=10, ge=1, le=50, description="Máximo de resultados por tipo"),
):
    """Jugadores, clubes y equipos (participaciones por temporada) cuyo nombre contiene el texto."""
    return season_service.search(cur, q, limit)
