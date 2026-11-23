from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import NamedRef


class StatHigh(BaseModel):
    value: float | None = None
    match_id: int | None = None
    # contexto del partido, para no tener que abrirlo
    date: str | None = None
    season: str | None = None
    competition: str | None = None
    round: int | None = None
    team: NamedRef | None = None  # equipo del jugador (o el propio equipo) en ese partido
    opponent: NamedRef | None = None
    score: str | None = None  # "81-71", primero su equipo
    result: str | None = None  # "V" / "D"


class PlayerGameHighs(BaseModel):
    points: StatHigh
    rebounds: StatHigh
    assists: StatHigh
    steals: StatHigh
    blocks: StatHigh
    three_pointers_made: StatHigh
    field_goals_made: StatHigh
    free_throws_made: StatHigh
    plus_minus: StatHigh
    rating: StatHigh
    seconds_played: StatHigh


class TeamGameHighs(BaseModel):
    points: StatHigh
    opponent_points: StatHigh
    margin: StatHigh  # points - opponent_points
    rebounds: StatHigh
    assists: StatHigh
    steals: StatHigh
    blocks: StatHigh
    three_pointers_made: StatHigh
    field_goals_made: StatHigh
    net_rating: StatHigh
