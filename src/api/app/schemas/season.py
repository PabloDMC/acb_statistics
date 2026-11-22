"""
Schemas de temporada: catálogo de ediciones, clasificación, medias de tiro de la liga y
búsqueda. Son las piezas "de temporada" que la capa de consumo necesita para los selectores y
la página de temporada.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import CompetitionContext, NamedRef


class PhaseInfo(BaseModel):
    code: str  # LR, PO, CR, SC...
    name: str | None = None
    matches: int
    first_date: str | None = None
    last_date: str | None = None


class CompetitionInfo(BaseModel):
    id: int
    name: str | None = None
    phases: list[PhaseInfo]


class EditionInfo(BaseModel):
    id: int
    name: str | None = None  # "2025-2026"
    start_year: int | None = None
    competitions: list[CompetitionInfo]


class StandingRow(BaseModel):
    position: int
    team: NamedRef
    club: NamedRef
    abbr: str | None = None
    logo: str | None = None
    games: int
    wins: int
    losses: int
    win_pct: float | None = None
    points_for: int
    points_against: int
    point_diff: int
    home_wins: int
    home_losses: int
    away_wins: int
    away_losses: int
    streak: str | None = None  # "G3" = 3 victorias seguidas, "P2" = 2 derrotas
    last5: str | None = None  # de más antiguo a más reciente, p. ej. "GGPGG"


class Standings(BaseModel):
    context: CompetitionContext
    round: int | None = None  # jornada tras la que se calcula (None = todas las jugadas)
    tiebreak: str
    rows: list[StandingRow]


class RoundPosition(BaseModel):
    team_id: int
    position: int
    wins: int
    losses: int


class StandingsRound(BaseModel):
    round: int
    positions: list[RoundPosition]


class StandingsHistory(BaseModel):
    context: CompetitionContext
    teams: list[StandingRow]  # clasificación final, para nombres, logos y orden de la leyenda
    rounds: list[StandingsRound]


class LeagueZone(BaseModel):
    zone_id: int | None = None
    zone: str | None = None
    area: str | None = None
    range: str | None = None
    attempted: int
    made: int
    pct: float | None = None
    frequency: float | None = None


class SearchHit(BaseModel):
    type: str  # player | club | team
    id: int
    name: str | None = None
    detail: str | None = None  # equipo actual del jugador, temporada del equipo...
    extra_id: int | None = None  # club_id del equipo, team_id actual del jugador


class SearchResults(BaseModel):
    query: str
    players: list[SearchHit]
    clubs: list[SearchHit]
    teams: list[SearchHit]
