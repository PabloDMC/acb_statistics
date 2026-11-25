from __future__ import annotations

import duckdb

from app.repositories import stats_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.stats import PlayerStatsRow, TeamStatsRow
from app.services.mappers import competition_context

_PLAYER_STATS = stats_repo.PLAYER_COUNT_COLUMNS + stats_repo.PLAYER_RATE_COLUMNS + stats_repo.PLAYER_RAW_COLUMNS
_TEAM_STATS = stats_repo.TEAM_COUNT_COLUMNS + stats_repo.TEAM_RATE_COLUMNS + stats_repo.TEAM_RAW_COLUMNS


def player_stats(
    cur: duckdb.DuckDBPyConnection,
    filters: CompetitionFilters,
    per: str,
    min_games: int,
    page: PageParams,
    player_id: int | None = None,
    min_minutes: float = 0,
) -> tuple[list[PlayerStatsRow], int]:
    rows, total = stats_repo.player_stats(cur, filters, per, min_games, page, player_id, min_minutes)
    items = [
        PlayerStatsRow(
            player={"id": r["player_id"], "name": r.get("name")},
            position=r.get("position"),
            club_team={
                "club": {"id": r.get("club_id"), "name": r.get("club_name")},
                "team": {"id": r.get("team_id"), "name": r.get("team_name")},
            },
            context=competition_context(r),
            games=r.get("games") or 0,
            games_started=r.get("games_started"),
            minutes=r.get("minutes"),
            stats={c: r.get(c) for c in _PLAYER_STATS},
        )
        for r in rows
    ]
    return items, total


def team_stats(
    cur: duckdb.DuckDBPyConnection, filters: CompetitionFilters, per: str, page: PageParams
) -> tuple[list[TeamStatsRow], int]:
    rows, total = stats_repo.team_stats(cur, filters, per, page)
    items = [
        TeamStatsRow(
            club_team={
                "club": {"id": r.get("club_id"), "name": r.get("club_name")},
                "team": {"id": r.get("team_id"), "name": r.get("name")},
            },
            context=competition_context(r),
            abbr=r.get("abbr"),
            logo=r.get("logo"),
            games=r.get("games") or 0,
            wins=r.get("wins"),
            losses=r.get("losses"),
            stats={c: r.get(c) for c in _TEAM_STATS},
        )
        for r in rows
    ]
    return items, total
