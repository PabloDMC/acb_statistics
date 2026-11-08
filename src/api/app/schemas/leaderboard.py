from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ClubTeamRef, CompetitionContext, NamedRef

# Métricas soportadas en /leaderboards/players y /teams. Mantener esta lista
# como única fuente de verdad evita "endpoints diferentes para cada
# estadística" (ver punto 28/30 del resumen original del proyecto).
# Cubre prácticamente todas las columnas de agg_player_totals / agg_team_totals.
PLAYER_LEADERBOARD_METRICS: dict[str, str] = {
    # producción
    "points": "points",
    "assists": "assists",
    "rebounds": "total_rebounds",
    "offensive_rebounds": "off_rebounds",
    "defensive_rebounds": "def_rebounds",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
    "personal_fouls": "personal_fouls",
    "fouls_drawn": "fouls_drawn",
    "plus_minus": "plus_minus",
    "rating": "rating",
    "double_doubles": "is_double_double",
    "triple_doubles": "is_triple_double",
    "seconds_played": "seconds",
    # tiro
    "field_goals_made": "field_goals_made",
    "field_goals_pct": "field_goals_pct",
    "two_pointers_made": "two_pointers_made",
    "two_pointers_pct": "two_pointers_pct",
    "three_pointers_made": "three_pointers_made",
    "three_pointers_pct": "three_pointers_pct",
    "free_throws_made": "free_throws_made",
    "free_throws_pct": "free_throws_pct",
    "effective_field_goals_pct": "effective_field_goals_pct",
    "true_shooting_pct": "true_shooting_pct",
    "dunks": "dunks",
    # impacto
    "offensive_rating": "offensive_rating",  # on-court
    "defensive_rating": "defensive_rating",
    "net_rating": "net_rating",
    "onoff_offensive_rating": "onoff_offensive_rating",
    "onoff_defensive_rating": "onoff_defensive_rating",
    "onoff_net_rating": "onoff_net_rating",
}

TEAM_LEADERBOARD_METRICS: dict[str, str] = {
    "points": "points",
    "opponent_points": "opponent_points",
    "rebounds": "total_rebounds",
    "offensive_rebounds": "off_rebounds",
    "defensive_rebounds": "def_rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
    "personal_fouls": "personal_fouls",
    "fouls_drawn": "fouls_drawn",
    "rating": "rating",
    "field_goals_made": "field_goals_made",
    "field_goals_pct": "field_goals_pct",
    "two_pointers_made": "two_pointers_made",
    "two_pointers_pct": "two_pointers_pct",
    "three_pointers_made": "three_pointers_made",
    "three_pointers_pct": "three_pointers_pct",
    "free_throws_made": "free_throws_made",
    "free_throws_pct": "free_throws_pct",
    "effective_field_goals_pct": "effective_field_goals_pct",
    "true_shooting_pct": "true_shooting_pct",
    "dunks": "dunks",
    "offensive_rating": "offensive_rating",
    "defensive_rating": "defensive_rating",
    "net_rating": "net_rating",
}

# Métricas "contables" (admiten SUM y por tanto escalado per_game/per_100_poss/
# per_40_min). Las de ratio (pct, ratings) no se escalan por partido/minuto:
# ya son una tasa en sí misma.
PLAYER_COUNTABLE_METRICS: set[str] = {
    "points", "assists", "rebounds", "offensive_rebounds", "defensive_rebounds",
    "steals", "blocks", "turnovers", "personal_fouls", "fouls_drawn", "plus_minus",
    "rating", "double_doubles", "triple_doubles", "field_goals_made",
    "two_pointers_made", "three_pointers_made", "free_throws_made", "dunks",
}
TEAM_COUNTABLE_METRICS: set[str] = {
    "points", "opponent_points", "rebounds", "offensive_rebounds", "defensive_rebounds",
    "assists", "steals", "blocks", "turnovers", "personal_fouls", "fouls_drawn",
    "rating", "field_goals_made", "two_pointers_made", "three_pointers_made",
    "free_throws_made", "dunks",
}

# Para scope=career: cómo agregar cada métrica de ratio a través de varias
# filas (ediciones/fases) en vez de un AVG mal ponderado. Las contables usan
# SUM (no hace falta entrada aquí).
PLAYER_CAREER_RATE_FORMULAS: dict[str, str] = {
    "field_goals_pct": "SUM(t.field_goals_made) / NULLIF(SUM(t.field_goals_attempted), 0)",
    "two_pointers_pct": "SUM(t.two_pointers_made) / NULLIF(SUM(t.two_pointers_attempted), 0)",
    "three_pointers_pct": "SUM(t.three_pointers_made) / NULLIF(SUM(t.three_pointers_attempted), 0)",
    "free_throws_pct": "SUM(t.free_throws_made) / NULLIF(SUM(t.free_throws_attempted), 0)",
    "effective_field_goals_pct": (
        "(SUM(t.field_goals_made) + 0.5 * SUM(t.three_pointers_made)) "
        "/ NULLIF(SUM(t.field_goals_attempted), 0)"
    ),
    "true_shooting_pct": (
        "SUM(t.points) / NULLIF(2.0 * (SUM(t.field_goals_attempted) "
        "+ 0.44 * SUM(t.free_throws_attempted)), 0)"
    ),
    "offensive_rating": "100.0 * SUM(t.team_points) / NULLIF(SUM(t.offensive_possessions), 0)",
    "defensive_rating": "100.0 * SUM(t.opp_points) / NULLIF(SUM(t.defensive_possessions), 0)",
    "net_rating": (
        "(100.0 * SUM(t.team_points) / NULLIF(SUM(t.offensive_possessions), 0)) - "
        "(100.0 * SUM(t.opp_points) / NULLIF(SUM(t.defensive_possessions), 0))"
    ),
    # On/off exacto: rating con el jugador en pista menos rating con él en el
    # banquillo, sumando puntos y posesiones de todas las filas (agg_player_totals
    # expone las columnas off_* precisamente para esto).
    "onoff_offensive_rating": (
        "(100.0 * SUM(t.team_points) / NULLIF(SUM(t.offensive_possessions), 0)) - "
        "(100.0 * SUM(t.off_team_points) / NULLIF(SUM(t.off_offensive_possessions), 0))"
    ),
    "onoff_defensive_rating": (
        "(100.0 * SUM(t.opp_points) / NULLIF(SUM(t.defensive_possessions), 0)) - "
        "(100.0 * SUM(t.off_opp_points) / NULLIF(SUM(t.off_defensive_possessions), 0))"
    ),
    "onoff_net_rating": (
        "((100.0 * SUM(t.team_points) / NULLIF(SUM(t.offensive_possessions), 0)) - "
        "(100.0 * SUM(t.opp_points) / NULLIF(SUM(t.defensive_possessions), 0))) - "
        "((100.0 * SUM(t.off_team_points) / NULLIF(SUM(t.off_offensive_possessions), 0)) - "
        "(100.0 * SUM(t.off_opp_points) / NULLIF(SUM(t.off_defensive_possessions), 0)))"
    ),
}
TEAM_CAREER_RATE_FORMULAS: dict[str, str] = {
    "field_goals_pct": "SUM(t.field_goals_made) / NULLIF(SUM(t.field_goals_attempted), 0)",
    "two_pointers_pct": "SUM(t.two_pointers_made) / NULLIF(SUM(t.two_pointers_attempted), 0)",
    "three_pointers_pct": "SUM(t.three_pointers_made) / NULLIF(SUM(t.three_pointers_attempted), 0)",
    "free_throws_pct": "SUM(t.free_throws_made) / NULLIF(SUM(t.free_throws_attempted), 0)",
    "effective_field_goals_pct": (
        "(SUM(t.field_goals_made) + 0.5 * SUM(t.three_pointers_made)) "
        "/ NULLIF(SUM(t.field_goals_attempted), 0)"
    ),
    "true_shooting_pct": (
        "SUM(t.points) / NULLIF(2.0 * (SUM(t.field_goals_attempted) "
        "+ 0.44 * SUM(t.free_throws_attempted)), 0)"
    ),
    # `possessions` es ataque + defensa: el rating ofensivo se divide entre las
    # posesiones de ataque y el defensivo entre las de defensa (antes ambos se
    # dividían entre el total y salían a la mitad).
    # possession_points: solo los puntos de partidos con posesiones (ver agg_team_totals).
    "offensive_rating": "100.0 * SUM(t.possession_points) / NULLIF(SUM(t.offensive_possessions), 0)",
    "defensive_rating": "100.0 * SUM(t.possession_opponent_points) / NULLIF(SUM(t.defensive_possessions), 0)",
    "net_rating": (
        "(100.0 * SUM(t.possession_points) / NULLIF(SUM(t.offensive_possessions), 0)) - "
        "(100.0 * SUM(t.possession_opponent_points) / NULLIF(SUM(t.defensive_possessions), 0))"
    ),
}

# Leaderboards de tiro (zona y/o clutch). metric -> columna/expresión sobre
# fact_shots agregado por jugador, o sobre agg_player_shooting_zones cuando
# no hace falta filtrar por clutch (ver leaderboard_repo.shooting_leaderboard).
SHOOTING_LEADERBOARD_METRICS: set[str] = {"made", "attempted", "pct", "frequency"}


# Tipos para los parámetros de query: FastAPI valida el valor y lo documenta en
# OpenAPI sin validación manual en el service.
PlayerMetric = Enum("PlayerMetric", {k: k for k in PLAYER_LEADERBOARD_METRICS}, type=str)
TeamMetric = Enum("TeamMetric", {k: k for k in TEAM_LEADERBOARD_METRICS}, type=str)
ShootingMetric = Enum("ShootingMetric", {k: k for k in sorted(SHOOTING_LEADERBOARD_METRICS)}, type=str)
LeaderboardScope = Literal["season", "career"]
LeaderboardPer = Literal["total", "per_game", "per_100_poss", "per_40_min"]


class PlayerLeaderboardEntry(BaseModel):
    rank: int
    player: NamedRef
    club_team: ClubTeamRef
    context: CompetitionContext
    value: float


class TeamLeaderboardEntry(BaseModel):
    rank: int
    club_team: ClubTeamRef
    context: CompetitionContext
    value: float


class ShootingLeaderboardEntry(BaseModel):
    rank: int
    player: NamedRef
    club_team: ClubTeamRef
    # edición/competición/fase que cubre la entrada; edition = "Carrera" si suma varias temporadas
    context: CompetitionContext
    zone: str | None = None  # None = todas las zonas combinadas
    clutch_only: bool
    made: int
    attempted: int
    pct: float | None = None
    value: float
