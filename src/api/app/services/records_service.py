from __future__ import annotations

import duckdb

from app.repositories import common_repo, records_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.records import AssistPairEntry, ClutchLeaderboardEntry, GameRecordEntry


def _date(value) -> str | None:
    return value[:10] if isinstance(value, str) else None


def clutch_leaderboard(
    cur: duckdb.DuckDBPyConnection, metric: str, filters: CompetitionFilters, min_attempts: int, page: PageParams
) -> list[ClutchLeaderboardEntry]:
    rows = records_repo.clutch_leaderboard(cur, metric, filters, min_attempts, page)
    names = common_repo.player_names_batch(cur, [r["player_id"] for r in rows], filters.edition_id)
    teams = records_repo.team_names(cur, [r["team_id"] for r in rows])
    return [
        ClutchLeaderboardEntry(
            rank=page.offset + i,
            player={"id": r["player_id"], "name": names.get(r["player_id"])},
            team={"id": r["team_id"], "name": teams.get(r["team_id"])},
            games=r["games"] or 0,
            value=r.get(metric),
            stats={k: v for k, v in r.items() if k not in ("player_id", "team_id")},
        )
        for i, r in enumerate(rows, start=1)
    ]


def game_records(
    cur: duckdb.DuckDBPyConnection, target: str, metric: str, filters: CompetitionFilters, page: PageParams
) -> list[GameRecordEntry]:
    if target == "teams":
        rows = records_repo.team_game_records(cur, metric, filters, page)
    else:
        rows = records_repo.player_game_records(cur, metric, filters, page)
    out = []
    for i, r in enumerate(rows, start=1):
        if r.get("value") is None:
            continue
        value = r["value"] / 60 if metric == "seconds" else r["value"]
        out.append(GameRecordEntry(
            rank=page.offset + i,
            match_id=r["match_id"],
            player={"id": r["player_id"], "name": r.get("player_name")} if target != "teams" else None,
            team={"id": r["team_id"], "name": r.get("team_name")},
            opponent={"id": r.get("opponent_team_id"), "name": r.get("opponent_team_name")},
            date=_date(r.get("date")),
            season=r.get("season_name"),
            competition=r.get("competition_name"),
            round=r.get("round_number"),
            score=(f"{r['team_points']}-{r['opponent_points']}"
                   if r.get("team_points") is not None and r.get("opponent_points") is not None else None),
            result=None if r.get("is_win") is None else ("V" if r["is_win"] else "D"),
            value=value,
        ))
    return out


def assist_pairs(
    cur: duckdb.DuckDBPyConnection, filters: CompetitionFilters, kind: str, sort: str, page: PageParams
) -> list[AssistPairEntry]:
    rows = records_repo.assist_pairs(cur, filters, kind, sort, page)
    ids = [r["assist_player_id"] for r in rows] + [r["scorer_player_id"] for r in rows]
    names = common_repo.player_names_batch(cur, ids, filters.edition_id)
    teams = records_repo.team_names(cur, [r["team_id"] for r in rows])
    return [
        AssistPairEntry(
            rank=page.offset + i,
            assister={"id": r["assist_player_id"], "name": names.get(r["assist_player_id"])},
            scorer={"id": r["scorer_player_id"], "name": names.get(r["scorer_player_id"])},
            team={"id": r["team_id"], "name": teams.get(r["team_id"])},
            assisted_plays=r["assisted_plays"],
            points=r["points"] or 0,
            two_pointers=r["two_pointers"],
            three_pointers=r["three_pointers"],
            free_throw_trips=r["free_throw_trips"],
        )
        for i, r in enumerate(rows, start=1)
    ]
