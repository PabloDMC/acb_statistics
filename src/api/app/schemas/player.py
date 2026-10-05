"""
Schemas de Players.

Nota: los campos numéricos usan `float | None` con default None salvo que
sean claramente enteros de conteo (partidos, ids). Esto hace los modelos
tolerantes a columnas que en la BBDD real puedan faltar o venir como NULL,
sin romper la validación de FastAPI. Ajusta tipos/nombres si al inspeccionar
tu esquema real (ver scripts/inspect_schema.py) hay diferencias.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import ClubTeamRef, CompetitionContext, NamedRef


class PlayerSummary(BaseModel):
    id: int
    name: str
    current_team: NamedRef | None = None
    current_club: NamedRef | None = None


class PlayerBasicInfo(BaseModel):
    """
    El warehouse actual no tiene bio de jugador (nacimiento, nacionalidad,
    posición, altura) en ningún sitio — no se ingiere todavía desde la API
    de la ACB. Si algún día se añade, este es el sitio natural para meterlo.
    """

    id: int
    name: str
    shirt_number: str | None = None
    headshot_image_url: str | None = None


# ---- Producción / totales (agg_player_totals) --------------------------------

class ShootingSplit(BaseModel):
    made: int | None = None
    attempted: int | None = None
    pct: float | None = None


class PlayerTotals(BaseModel):
    context: CompetitionContext
    club_team: ClubTeamRef

    games_played: int | None = None
    games_started: int | None = None
    seconds: int | None = None

    points: float | None = None
    assists: float | None = None
    rebounds: float | None = None
    steals: float | None = None
    turnovers: float | None = None
    blocks: float | None = None
    personal_fouls: float | None = None
    fouls_drawn: float | None = None
    rating: float | None = None

    field_goals: ShootingSplit
    two_pointers: ShootingSplit
    three_pointers: ShootingSplit
    free_throws: ShootingSplit

    effective_field_goal_pct: float | None = None
    true_shooting_pct: float | None = None

    double_doubles: int | None = None
    triple_doubles: int | None = None


# ---- Partido a partido (fact_player_games) ------------------------------------

class PlayerGameLogEntry(BaseModel):
    match_id: int
    context: CompetitionContext
    opponent: NamedRef | None = None
    is_home: bool | None = None

    seconds: int | None = None
    points: float | None = None
    assists: float | None = None
    rebounds: float | None = None
    steals: float | None = None
    turnovers: float | None = None
    blocks: float | None = None
    plus_minus: float | None = None
    rating: float | None = None

    field_goals: ShootingSplit
    three_pointers: ShootingSplit
    free_throws: ShootingSplit


# ---- Shooting (agg_player_shooting) -------------------------------------------

class ZoneShooting(BaseModel):
    zone: str
    attempted: int | None = None
    made: int | None = None
    pct: float | None = None
    frequency: float | None = None


class AssistedShare(BaseModel):
    assisted_made: int | None = None
    unassisted_made: int | None = None
    assisted_pct: float | None = None


class PlayerShootingProfile(BaseModel):
    context: CompetitionContext
    club_team: ClubTeamRef

    field_goals: ShootingSplit
    two_pointers: ShootingSplit
    three_pointers: ShootingSplit
    free_throws: ShootingSplit
    dunks: ShootingSplit

    zones: list[ZoneShooting] = []

    assisted_field_goals: AssistedShare
    assisted_two_pointers_made: int | None = None
    assisted_three_pointers_made: int | None = None
    assisted_dunks: int | None = None
    unassisted_dunks: int | None = None

    and_ones: int | None = None


# ---- On-court / On-off ---------------------------------------------------------

class PlayerImpact(BaseModel):
    context: CompetitionContext
    on_court_plus_minus_per_100: float | None = None
    on_court_offensive_rating: float | None = None
    on_court_defensive_rating: float | None = None
    on_court_net_rating: float | None = None
    off_court_net_rating: float | None = None
    on_off_net_rating: float | None = None
    possessions_on_court: int | None = None


# ---- Lineups en los que participa ---------------------------------------------

class PlayerLineupParticipation(BaseModel):
    lineup_id: str
    teammates: list[NamedRef]
    minutes: float | None = None
    possessions: int | None = None
    offensive_rating: float | None = None
    defensive_rating: float | None = None
    net_rating: float | None = None
    plus_minus: float | None = None


# ---- Perfil compuesto para la página estilo Basketball-Reference --------------

class PlayerProfile(BaseModel):
    """
    Endpoint "BFF" pensado para pintar de una sola llamada la página de
    jugador que se describe en el punto 32 del resumen: perfil, producción,
    eficiencia, impacto y shooting. Streamlit no debería tener que hacer
    5-6 llamadas para una sola pantalla.
    """

    player: PlayerBasicInfo
    context: CompetitionContext
    club_team: ClubTeamRef

    totals: PlayerTotals | None = None
    shooting: PlayerShootingProfile | None = None
    impact: PlayerImpact | None = None
    top_lineups: list[PlayerLineupParticipation] = []
