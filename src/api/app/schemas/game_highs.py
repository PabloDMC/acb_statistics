from __future__ import annotations

from pydantic import BaseModel


class StatHigh(BaseModel):
    value: float | None = None
    match_id: int | None = None


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
