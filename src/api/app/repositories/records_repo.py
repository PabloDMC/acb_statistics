"""Rankings de clutch, récords en un partido y parejas anotador-asistente."""

from __future__ import annotations

import duckdb

from app.core.serialization import cursor_to_dicts
from app.repositories.base import SQLFilterBuilder, pagination_sql
from app.schemas.common import CompetitionFilters, PageParams

CLUTCH_SUMS = [
    "games", "points", "field_goals_made", "field_goals_attempted", "three_pointers_made",
    "three_pointers_attempted", "free_throws_made", "free_throws_attempted", "off_rebounds",
    "def_rebounds", "total_rebounds", "assists", "steals", "blocks", "turnovers",
]
_PCT = {
    "field_goals_pct": ("field_goals_made", "field_goals_attempted"),
    "three_pointers_pct": ("three_pointers_made", "three_pointers_attempted"),
    "free_throws_pct": ("free_throws_made", "free_throws_attempted"),
}


def _filters(alias: str, filters: CompetitionFilters) -> SQLFilterBuilder:
    fb = SQLFilterBuilder(table_alias=alias)
    fb.add_competition_filters(filters)
    return fb


def clutch_leaderboard(
    cur: duckdb.DuckDBPyConnection, metric: str, filters: CompetitionFilters, min_attempts: int, page: PageParams
) -> list[dict]:
    fb = _filters("c", filters)
    sums = ",\n".join(f"SUM(c.{col}) AS {col}" for col in CLUTCH_SUMS)
    pct_cols = ",\n".join(f"SUM(c.{m}) * 1.0 / NULLIF(SUM(c.{a}), 0) AS {name}" for name, (m, a) in _PCT.items())
    having = ""
    params = list(fb.params)
    if metric in _PCT:
        having = f"HAVING SUM(c.{_PCT[metric][1]}) >= ?"
        params.append(min_attempts)
    cur.execute(
        f"""
        SELECT * FROM (
            SELECT
                c.player_id,
                arg_max(c.team_id, c.edition_id) AS team_id,
                {sums},
                {pct_cols}
            FROM main_marts.agg_player_clutch c
            {fb.where_sql()}
            GROUP BY c.player_id
            {having}
        )
        WHERE {metric} IS NOT NULL
        ORDER BY {metric} DESC, games ASC, player_id
        {pagination_sql(page)}
        """,
        params,
    )
    return cursor_to_dicts(cur)


def player_game_records(
    cur: duckdb.DuckDBPyConnection, metric: str, filters: CompetitionFilters, page: PageParams
) -> list[dict]:
    fb = _filters("g", filters)
    fb.clauses.append("g.seconds > 0")
    cur.execute(
        f"""
        SELECT g.match_id, g.player_id, trim(g.player_name) AS player_name, g.team_id, g.team_name,
               g.opponent_team_id, g.opponent_team_name, g.team_points, g.opponent_points, g.is_win,
               m.match_start_time AS date, m.round_number, e.season_name, c.competition_name,
               g.{metric} AS value
        FROM main_marts.fact_player_games g
        LEFT JOIN main_marts.dim_matches m ON m.match_id = g.match_id
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = g.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = g.competition_id
        {fb.where_sql()}
        ORDER BY value DESC NULLS LAST, m.match_start_time
        {pagination_sql(page)}
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


def team_game_records(
    cur: duckdb.DuckDBPyConnection, metric: str, filters: CompetitionFilters, page: PageParams
) -> list[dict]:
    fb = _filters("g", filters)
    fb.clauses.append("g.points IS NOT NULL AND g.points + g.opponent_points > 0")
    expr = "g.points - g.opponent_points" if metric == "margin" else f"g.{metric}"
    cur.execute(
        f"""
        SELECT g.match_id, g.team_id, g.team_name, g.opponent_team_id, g.opponent_team_name,
               g.points AS team_points, g.opponent_points, g.is_win,
               m.match_start_time AS date, m.round_number, e.season_name, c.competition_name,
               {expr} AS value
        FROM main_marts.fact_team_games g
        LEFT JOIN main_marts.dim_matches m ON m.match_id = g.match_id
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = g.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = g.competition_id
        {fb.where_sql()}
        ORDER BY value DESC NULLS LAST, m.match_start_time
        {pagination_sql(page)}
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


def assist_pairs(
    cur: duckdb.DuckDBPyConnection, filters: CompetitionFilters, kind: str, sort: str, page: PageParams
) -> list[dict]:
    fb = _filters("a", filters)
    if kind != "all":
        fb.add("play_kind", kind)
    order = "points DESC, assisted_plays DESC" if sort == "points" else "assisted_plays DESC, points DESC"
    cur.execute(
        f"""
        SELECT
            a.assist_player_id, a.scorer_player_id,
            arg_max(a.team_id, a.edition_id) AS team_id,
            count(*) AS assisted_plays,
            sum(a.points) AS points,
            count(*) FILTER (WHERE a.play_kind = '2P') AS two_pointers,
            count(*) FILTER (WHERE a.play_kind = '3P') AS three_pointers,
            count(*) FILTER (WHERE a.play_kind = 'FT') AS free_throw_trips
        FROM main_marts.fact_assisted_plays a
        {fb.where_sql()}
        GROUP BY a.assist_player_id, a.scorer_player_id
        ORDER BY {order}, a.assist_player_id, a.scorer_player_id
        {pagination_sql(page)}
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


def team_names(cur: duckdb.DuckDBPyConnection, team_ids: list[int]) -> dict[int, str]:
    ids = [i for i in dict.fromkeys(team_ids) if i is not None]
    if not ids:
        return {}
    cur.execute(
        f"SELECT team_id, any_value(full_name) AS name FROM main_marts.dim_teams WHERE team_id IN ({','.join('?' for _ in ids)}) GROUP BY team_id",
        ids,
    )
    return {r["team_id"]: r["name"] for r in cursor_to_dicts(cur)}
