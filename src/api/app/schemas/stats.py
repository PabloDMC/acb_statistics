"""
Tablas de estadísticas de temporada (al estilo de las páginas "Player Stats" / "Team Stats"
de Basketball Reference): una fila por jugador o equipo con TODAS las columnas, para pintarlas
como tabla ordenable. Las columnas de estadística van en `stats` (dict plano) para que la capa
de consumo las convierta directamente en un DataFrame (`pd.json_normalize`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ClubTeamRef, CompetitionContext, NamedRef

PlayerStatsPer = Literal["total", "per_game", "per_36", "per_100"]
TeamStatsPer = Literal["total", "per_game", "per_100"]


class PlayerStatsRow(BaseModel):
    player: NamedRef
    club_team: ClubTeamRef
    context: CompetitionContext
    games: int
    games_started: int | None = None
    minutes: float | None = None  # totales o por partido según `per`
    stats: dict[str, float | int | None]


class TeamStatsRow(BaseModel):
    club_team: ClubTeamRef
    context: CompetitionContext
    abbr: str | None = None
    logo: str | None = None
    games: int
    wins: int | None = None
    losses: int | None = None
    stats: dict[str, float | int | None]
