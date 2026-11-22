from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import ClubTeamRef, CompetitionContext, NamedRef


class TeamSummary(BaseModel):
    team: NamedRef
    club: NamedRef


class TeamTotals(BaseModel):
    context: CompetitionContext
    club_team: ClubTeamRef

    games_played: int | None = None
    wins: int | None = None
    losses: int | None = None

    points_for: float | None = None
    points_against: float | None = None

    possessions: float | None = None
    offensive_rating: float | None = None
    defensive_rating: float | None = None
    net_rating: float | None = None

    # totales de tiro, rebote, etc. del equipo y del rival (opp_*), ritmo y four factors
    stats: dict[str, float | int | None] = {}


class TeamGameLogEntry(BaseModel):
    match_id: int
    context: CompetitionContext
    opponent: NamedRef | None = None
    is_home: bool | None = None
    result: str | None = None

    points_for: float | None = None
    points_against: float | None = None
    possessions: float | None = None
    offensive_rating: float | None = None
    defensive_rating: float | None = None
    net_rating: float | None = None


class LineupCombination(BaseModel):
    """Ver punto 23 del resumen: combinaciones de 2 a 5 jugadores."""

    combination_size: int
    players: list[NamedRef]
    minutes: float | None = None
    possessions: int | None = None
    offensive_rating: float | None = None
    defensive_rating: float | None = None
    net_rating: float | None = None
    plus_minus: float | None = None


class RotationMinute(BaseModel):
    minute: int  # 0 a 39 (minuto de partido, sin prórrogas)
    games_on_court: int
    pct_games_on_court: float | None = None  # sobre los partidos del equipo con play-by-play
    avg_seconds: float | None = None  # segundos medios en pista en ese minuto (0-60)


class PlayerRotation(BaseModel):
    player: NamedRef
    player_games: int
    total_seconds: int
    minutes: list[RotationMinute]  # siempre 40 entradas, de 0 a 39


class TeamRotations(BaseModel):
    team: NamedRef
    team_games: int
    players: list[PlayerRotation]  # ordenados por segundos totales en pista
