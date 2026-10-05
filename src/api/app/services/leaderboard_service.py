from __future__ import annotations

import duckdb
from fastapi import HTTPException

from app.repositories import common_repo, leaderboard_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.leaderboard import (
    PLAYER_COUNTABLE_METRICS,
    PLAYER_LEADERBOARD_METRICS,
    SHOOTING_LEADERBOARD_METRICS,
    TEAM_COUNTABLE_METRICS,
    TEAM_LEADERBOARD_METRICS,
    PlayerLeaderboardEntry,
    ShootingLeaderboardEntry,
    TeamLeaderboardEntry,
)
from app.services.mappers import club_team_ref, competition_context

_VALID_SCOPES = {"season", "career"}
_VALID_PERS = {"total", "per_game", "per_100_poss", "per_40_min"}


def _validate_metric(metric: str, allowed: dict[str, str]) -> None:
    if metric not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Métrica '{metric}' no soportada. Opciones válidas: {sorted(allowed)}",
        )


def _validate_scope_and_per(scope: str, per: str, metric: str, countable: set[str]) -> None:
    if scope not in _VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"scope debe ser una de: {sorted(_VALID_SCOPES)}")
    if per not in _VALID_PERS:
        raise HTTPException(status_code=422, detail=f"per debe ser una de: {sorted(_VALID_PERS)}")
    if per != "total" and metric not in countable:
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{metric}' ya es una tasa (porcentaje/rating): 'per' solo aplica a "
                f"métricas contables ({sorted(countable)})."
            ),
        )


def player_leaderboard(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    filters: CompetitionFilters,
    page: PageParams,
    min_games: int,
    scope: str,
    per: str,
) -> list[PlayerLeaderboardEntry]:
    _validate_metric(metric, PLAYER_LEADERBOARD_METRICS)
    _validate_scope_and_per(scope, per, metric, PLAYER_COUNTABLE_METRICS)

    rows = leaderboard_repo.player_leaderboard(cur, metric, filters, page, min_games, scope, per)

    ids = [row["player_id"] for row in rows]
    edition_id = filters.edition_id if scope == "season" else None
    names_by_id = common_repo.player_names_batch(cur, ids, edition_id)

    return [
        PlayerLeaderboardEntry(
            rank=row["rank"],
            player={"id": row["player_id"], "name": names_by_id.get(row["player_id"])},
            club_team=club_team_ref(row),
            context=competition_context(row),
            value=row["value"],
        )
        for row in rows
    ]


def team_leaderboard(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    filters: CompetitionFilters,
    page: PageParams,
    scope: str,
    per: str,
) -> list[TeamLeaderboardEntry]:
    _validate_metric(metric, TEAM_LEADERBOARD_METRICS)
    _validate_scope_and_per(scope, per, metric, TEAM_COUNTABLE_METRICS)

    rows = leaderboard_repo.team_leaderboard(cur, metric, filters, page, scope, per)
    return [
        TeamLeaderboardEntry(
            rank=row["rank"],
            club_team=club_team_ref(row),
            context=competition_context(row),
            value=row["value"],
        )
        for row in rows
    ]


def shooting_leaderboard(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    zone: str | None,
    clutch_only: bool,
    filters: CompetitionFilters,
    min_attempts: int,
    page: PageParams,
) -> list[ShootingLeaderboardEntry]:
    if metric not in SHOOTING_LEADERBOARD_METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"metric debe ser una de: {sorted(SHOOTING_LEADERBOARD_METRICS)}",
        )
    if clutch_only and metric == "frequency":
        raise HTTPException(
            status_code=422,
            detail="metric='frequency' no está disponible todavía con clutch_only=True",
        )

    rows = leaderboard_repo.shooting_leaderboard(cur, metric, zone, clutch_only, filters, min_attempts, page)

    ids = [row["player_id"] for row in rows]
    names_by_id = common_repo.player_names_batch(cur, ids, filters.edition_id)

    return [
        ShootingLeaderboardEntry(
            rank=row["rank"],
            player={"id": row["player_id"], "name": names_by_id.get(row["player_id"])},
            club_team=club_team_ref(row),
            zone=zone,
            clutch_only=clutch_only,
            made=row["made"],
            attempted=row["attempted"],
            pct=(row["made"] / row["attempted"]) if row.get("attempted") else None,
            value=row["value"],
        )
        for row in rows
    ]


def available_shot_zones(cur: duckdb.DuckDBPyConnection) -> list[str]:
    return leaderboard_repo.available_shot_zones(cur)
