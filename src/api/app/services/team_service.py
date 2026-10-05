from __future__ import annotations

import duckdb

from app.repositories import common_repo, team_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.game_highs import StatHigh, TeamGameHighs
from app.schemas.team import LineupCombination, TeamGameLogEntry, TeamSummary, TeamTotals
from app.services.mappers import club_team_ref, competition_context, named_ref, shooting_split  # noqa: F401


def list_teams(
    cur: duckdb.DuckDBPyConnection,
    name_query: str | None,
    filters: CompetitionFilters,
    page: PageParams,
) -> tuple[list[TeamSummary], int]:
    rows, total = team_repo.list_teams(cur, name_query, filters, page)
    items = [
        TeamSummary(
            team={"id": row["id"], "name": row["name"]},
            club={"id": row.get("club_id"), "name": row.get("club_name")},
        )
        for row in rows
    ]
    return items, total


def get_totals(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters
) -> list[TeamTotals]:
    team_repo.require_basic_info(cur, team_id)
    rows = team_repo.get_totals(cur, team_id, filters)
    return [
        TeamTotals(
            context=competition_context(row),
            club_team=club_team_ref(row),
            games_played=row.get("games_played"),
            wins=row.get("wins"),
            losses=row.get("losses"),
            points_for=row.get("points_for"),
            points_against=row.get("points_against"),
            possessions=row.get("possessions"),
            offensive_rating=row.get("offensive_rating"),
            defensive_rating=row.get("defensive_rating"),
            net_rating=row.get("net_rating"),
        )
        for row in rows
    ]


def get_game_log(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters, page: PageParams
) -> tuple[list[TeamGameLogEntry], int]:
    team_repo.require_basic_info(cur, team_id)
    rows, total = team_repo.get_game_log(cur, team_id, filters, page)
    items = [
        TeamGameLogEntry(
            match_id=row["match_id"],
            context=competition_context(row),
            opponent=named_ref(row, "opponent_team_id", "opponent_team_name"),
            is_home=row.get("is_home"),
            result=row.get("result"),
            points_for=row.get("points_for"),
            points_against=row.get("points_against"),
            possessions=row.get("possessions"),
            offensive_rating=row.get("offensive_rating"),
            defensive_rating=row.get("defensive_rating"),
            net_rating=row.get("net_rating"),
        )
        for row in rows
    ]
    return items, total


def get_lineup_combinations(
    cur: duckdb.DuckDBPyConnection,
    team_id: int,
    filters: CompetitionFilters,
    combination_size: int | None,
    page: PageParams,
) -> tuple[list[LineupCombination], int]:
    team_repo.require_basic_info(cur, team_id)
    rows, total = team_repo.get_lineup_combinations(cur, team_id, filters, combination_size, page)

    # agg_lineup_combinations no trae nombres de jugador: se resuelven en lote.
    all_ids = {pid for row in rows for pid in (row.get("player_ids") or [])}
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), filters.edition_id)

    items = [
        LineupCombination(
            combination_size=row["combination_size"],
            players=[
                {"id": pid, "name": names_by_id.get(pid)}
                for pid in (row.get("player_ids") or [])
            ],
            minutes=row.get("minutes"),
            possessions=row.get("possessions"),
            offensive_rating=row.get("offensive_rating"),
            defensive_rating=row.get("defensive_rating"),
            net_rating=row.get("net_rating"),
            plus_minus=row.get("plus_minus"),
        )
        for row in rows
    ]
    return items, total


def get_game_highs(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters
) -> TeamGameHighs:
    team_repo.require_basic_info(cur, team_id)
    row = team_repo.get_game_highs(cur, team_id, filters)
    return TeamGameHighs(**{
        name: StatHigh(value=row.get(f"{name}_value"), match_id=row.get(f"{name}_match_id"))
        for name in TeamGameHighs.model_fields
    })
