from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import CompetitionContext, NamedRef


class MatchSummary(BaseModel):
    id: int
    context: CompetitionContext
    date: str | None = None
    home_team: NamedRef
    away_team: NamedRef
    home_score: int | None = None
    away_score: int | None = None
    venue: str | None = None


class ShotEvent(BaseModel):
    """
    Pensado específicamente para pintar shot charts (punto 33 del resumen):
    ligero, sin agregaciones, un evento por lanzamiento.
    """

    player: NamedRef
    match_id: int | None = None  # presente cuando el evento viene de un endpoint multi-partido
    x: float
    y: float
    made: bool
    value: int  # 2 o 3
    zone: str | None = None
    is_clutch: bool | None = None
    quarter: int | None = None
    seconds_remaining: int | None = None


class LineupStint(BaseModel):
    team: NamedRef
    quarter: int | None = None
    # Segundos RESTANTES del cuarto al empezar y al acabar el tramo (reloj de
    # partido, cuenta atrás): start_time > end_time.
    start_time: int | None = None
    end_time: int | None = None
    players: list[NamedRef]
    team_points: int | None = None
    opponent_points: int | None = None
    plus_minus: int | None = None
    offensive_possessions: int | None = None
    defensive_possessions: int | None = None
