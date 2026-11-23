"""
Rankings "especiales": clutch (totales), récords en un partido y parejas anotador-asistente.
Todos agregan las filas que cumplen los filtros: sin edition_id es el histórico de la liga, con
edition_id la temporada y con team_id/club_id el equipo.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.common import NamedRef

ClutchMetric = Literal[
    "points", "field_goals_made", "field_goals_attempted", "field_goals_pct",
    "three_pointers_made", "three_pointers_attempted", "three_pointers_pct",
    "free_throws_made", "free_throws_attempted", "free_throws_pct",
    "total_rebounds", "off_rebounds", "def_rebounds", "assists", "steals", "blocks", "turnovers", "games",
]
GameRecordMetric = Literal[
    "points", "total_rebounds", "off_rebounds", "def_rebounds", "assists", "steals", "blocks",
    "three_pointers_made", "field_goals_made", "free_throws_made", "rating", "plus_minus", "seconds", "turnovers",
]
TeamGameRecordMetric = Literal[
    "points", "opponent_points", "margin", "total_rebounds", "assists", "steals", "blocks",
    "three_pointers_made", "field_goals_made", "free_throws_made", "rating", "offensive_rating",
]
AssistKind = Literal["all", "2P", "3P", "FT"]


class ClutchLeaderboardEntry(BaseModel):
    rank: int
    player: NamedRef
    team: NamedRef | None = None  # el más reciente dentro de los filtros
    games: int
    value: float | None = None
    stats: dict[str, float | int | None]  # todas las columnas de clutch en totales


class GameRecordEntry(BaseModel):
    rank: int
    match_id: int
    player: NamedRef | None = None  # None en récords de equipo
    team: NamedRef
    opponent: NamedRef | None = None
    date: str | None = None
    season: str | None = None
    competition: str | None = None
    round: int | None = None
    score: str | None = None  # primero su equipo
    result: str | None = None
    value: float


class AssistPairEntry(BaseModel):
    rank: int
    assister: NamedRef
    scorer: NamedRef
    team: NamedRef | None = None
    assisted_plays: int  # canastas (o tandas de tiros libres) asistidas
    points: int
    two_pointers: int
    three_pointers: int
    free_throw_trips: int
