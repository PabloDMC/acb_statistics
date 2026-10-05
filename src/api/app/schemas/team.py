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
