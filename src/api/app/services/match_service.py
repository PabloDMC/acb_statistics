from __future__ import annotations

import duckdb

from app.repositories import common_repo, match_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.match import LineupStint, MatchSummary, ShotEvent
from app.services.mappers import competition_context


def _match_to_schema(row: dict) -> MatchSummary:
    return MatchSummary(
        id=row["id"],
        context=competition_context(row),
        date=row.get("date").isoformat() if hasattr(row.get("date"), "isoformat") else row.get("date"),
        home_team={"id": row["home_team_id"], "name": row.get("home_team_name")},
        away_team={"id": row["away_team_id"], "name": row.get("away_team_name")},
        home_score=row.get("home_score"),
        away_score=row.get("away_score"),
        venue=row.get("venue"),
    )


def get_match(cur: duckdb.DuckDBPyConnection, match_id: int) -> MatchSummary:
    row = match_repo.require_match(cur, match_id)
    return _match_to_schema(row)


def list_matches(
    cur: duckdb.DuckDBPyConnection, filters: CompetitionFilters, page: PageParams
) -> tuple[list[MatchSummary], int]:
    rows, total = match_repo.list_matches(cur, filters, page)
    return [_match_to_schema(r) for r in rows], total


def get_shots(
    cur: duckdb.DuckDBPyConnection,
    match_id: int,
    team_id: int | None,
    player_id: int | None,
    clutch_only: bool = False,
) -> list[ShotEvent]:
    match = match_repo.require_match(cur, match_id)
    rows = match_repo.get_shots(cur, match_id, team_id, player_id, clutch_only)

    all_ids = {row["player_id"] for row in rows if row.get("player_id") is not None}
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), match.get("edition_id"))

    return [
        ShotEvent(
            player={"id": row["player_id"], "name": names_by_id.get(row["player_id"])},
            x=row["x"],
            y=row["y"],
            made=row["made"],
            value=row["value"],
            zone=row.get("zone"),
            is_clutch=row.get("is_clutch"),
            quarter=row.get("quarter"),
            seconds_remaining=row.get("seconds_remaining"),
        )
        for row in rows
    ]


def get_lineup_stints(cur: duckdb.DuckDBPyConnection, match_id: int) -> list[LineupStint]:
    match = match_repo.require_match(cur, match_id)
    rows = match_repo.get_lineup_stints(cur, match_id)

    all_ids = {pid for row in rows for pid in (row.get("player_ids") or [])}
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), match.get("edition_id"))

    return [
        LineupStint(
            team={"id": row["team_id"], "name": row.get("team_full_name")},
            quarter=row.get("quarter"),
            start_time=row.get("start_time"),
            end_time=row.get("end_time"),
            players=[
                {"id": pid, "name": names_by_id.get(pid)}
                for pid in (row.get("player_ids") or [])
            ],
            team_points=row.get("team_points"),
            opponent_points=row.get("opp_points"),
            plus_minus=row.get("plus_minus"),
            offensive_possessions=row.get("offensive_possessions"),
            defensive_possessions=row.get("defensive_possessions"),
        )
        for row in rows
    ]
