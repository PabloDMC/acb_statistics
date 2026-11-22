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
    round: int | None = None  # jornada (o número de ronda en playoffs/copa)
    attendance: int | None = None
    home_coach: str | None = None
    away_coach: str | None = None
    referees: list[str] = []
    home_team_logo: str | None = None
    away_team_logo: str | None = None


class ShotEvent(BaseModel):
    """
    Pensado específicamente para pintar shot charts (punto 33 del resumen):
    ligero, sin agregaciones, un evento por lanzamiento.
    """

    player: NamedRef
    team_id: int | None = None
    match_id: int | None = None  # presente cuando el evento viene de un endpoint multi-partido
    # Coordenadas tal como las da el feed de la ACB (ver README, "Coordenadas de los tiros")
    x: float
    y: float
    made: bool
    value: int  # 2 o 3
    zone_id: int | None = None
    zone: str | None = None  # zona básica; con `area` (lado) y `range` (distancia) identifica la zona
    area: str | None = None
    range: str | None = None
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


class QuarterScore(BaseModel):
    quarter: int
    home: int | None = None  # puntos del cuarto (no acumulados)
    away: int | None = None


class BoxscorePlayer(BaseModel):
    player: NamedRef
    shirt_number: str | None = None
    is_starter: bool | None = None
    played: bool  # False = convocado sin jugar (0:00)
    seconds: int | None = None
    minutes: str | None = None  # "25:13", como en el boxscore oficial
    stats: dict[str, float | int | None]


class BoxscoreTeam(BaseModel):
    team: NamedRef
    coach: str | None = None
    players: list[BoxscorePlayer]
    totals: dict[str, float | int | None]  # totales oficiales (incluyen rebotes y pérdidas de equipo)


class Boxscore(BaseModel):
    match: MatchSummary
    quarters: list[QuarterScore]
    home: BoxscoreTeam
    away: BoxscoreTeam


class PlayByPlayEvent(BaseModel):
    event_idx: int
    quarter: int
    clock: str | None = None  # reloj del cuarto, "mm:ss" (cuenta atrás)
    seconds_remaining: int | None = None
    play_type_id: int | None = None
    play: str | None = None  # nombre de la jugada
    category: str | None = None
    sub_category: str | None = None
    team: NamedRef | None = None
    player: NamedRef | None = None
    points: int | None = None
    score_home: int | None = None
    score_away: int | None = None
    is_clutch: bool | None = None
    possession_id: int | None = None
    offense_team_id: int | None = None
    event_kind: str | None = None  # apuntes contables: technical_ft, bookkeeping_turnover...
