"""
Tablas de estadísticas de temporada (todas las columnas de agg_player_totals / agg_team_totals),
con escalado por partido, por 36 minutos o por 100 posesiones.

Las columnas que se escalan son las "contables"; los porcentajes, ratings y avanzadas ya son una
tasa y se devuelven tal cual.
"""

from __future__ import annotations

import duckdb

from app.core.serialization import cursor_to_dicts, scalar
from app.repositories.base import SQLFilterBuilder, pagination_sql
from app.schemas.common import CompetitionFilters, PageParams

PLAYER_COUNT_COLUMNS = [
    "points",
    "field_goals_made", "field_goals_attempted",
    "two_pointers_made", "two_pointers_attempted",
    "three_pointers_made", "three_pointers_attempted",
    "free_throws_made", "free_throws_attempted",
    "dunks", "assists", "off_rebounds", "def_rebounds", "total_rebounds",
    "steals", "turnovers", "blocks", "received_blocks",
    "personal_fouls", "fouls_drawn", "plus_minus", "rating",
]
PLAYER_RATE_COLUMNS = [
    "field_goals_pct", "two_pointers_pct", "three_pointers_pct", "free_throws_pct",
    "effective_field_goals_pct", "true_shooting_pct",
    "usage_pct", "assist_pct", "turnover_pct",
    "off_rebound_pct", "def_rebound_pct", "total_rebound_pct", "steal_pct", "block_pct",
    "offensive_rating", "defensive_rating", "net_rating",
    "onoff_offensive_rating", "onoff_defensive_rating", "onoff_net_rating",
]
PLAYER_RAW_COLUMNS = ["is_double_double", "is_triple_double", "offensive_possessions", "defensive_possessions"]

TEAM_OPP = [
    "field_goals_made", "field_goals_attempted", "two_pointers_made", "two_pointers_attempted",
    "three_pointers_made", "three_pointers_attempted", "free_throws_made", "free_throws_attempted",
    "assists", "off_rebounds", "def_rebounds", "total_rebounds", "steals", "turnovers", "blocks",
    "personal_fouls",
]
TEAM_COUNT_COLUMNS = [
    "points", "opponent_points",
    "field_goals_made", "field_goals_attempted",
    "two_pointers_made", "two_pointers_attempted",
    "three_pointers_made", "three_pointers_attempted",
    "free_throws_made", "free_throws_attempted",
    "dunks", "assists", "off_rebounds", "def_rebounds", "total_rebounds",
    "steals", "turnovers", "blocks", "received_blocks", "personal_fouls", "fouls_drawn", "rating",
    *[f"opp_{c}" for c in TEAM_OPP],
]
TEAM_RATE_COLUMNS = [
    "field_goals_pct", "two_pointers_pct", "three_pointers_pct", "free_throws_pct",
    "effective_field_goals_pct", "true_shooting_pct",
    "offensive_rating", "defensive_rating", "net_rating", "possessions_per_game",
    "four_factors_efg_pct", "four_factors_tov_pct", "four_factors_orb_pct", "four_factors_ft_rate",
    "opp_four_factors_efg_pct", "opp_four_factors_tov_pct", "opp_four_factors_orb_pct", "opp_four_factors_ft_rate",
]
TEAM_RAW_COLUMNS = ["offensive_possessions", "defensive_possessions", "games_with_possessions"]

_CONTEXT_JOINS = """
    LEFT JOIN main_marts.dim_editions e ON e.edition_id = t.edition_id
    LEFT JOIN main_marts.dim_competitions c ON c.competition_id = t.competition_id
"""


def _sort(sort: str | None, allowed: set[str], default: str) -> str:
    """Orden por cualquier columna de la tabla, como en el resto de la API: 'points' ascendente,
    '-points' descendente. Sin `sort`, la columna por defecto en descendente."""
    if not sort:
        return f"{default} DESC NULLS LAST"
    desc = sort.startswith("-")
    col = sort.lstrip("-")
    if col == "name":
        return f"lower(strip_accents(name)) {'DESC' if desc else 'ASC'}"
    if col not in allowed:
        return f"{default} DESC NULLS LAST"
    return f"{col} {'DESC' if desc else 'ASC'} NULLS LAST"


def player_stats(
    cur: duckdb.DuckDBPyConnection,
    filters: CompetitionFilters,
    per: str,
    min_games: int,
    page: PageParams,
    player_id: int | None = None,
) -> tuple[list[dict], int]:
    fb = SQLFilterBuilder(table_alias="t")
    fb.add_competition_filters(filters)
    fb.add("player_id", player_id)
    fb.clauses.append("t.games >= ?")
    fb.params.append(min_games)
    where_sql = fb.where_sql()

    keys = "edition_id, competition_id, competition_phase, player_id, team_id"
    poss_join = ""
    if per == "per_100":
        # por 100 posesiones: solo partidos con play-by-play (ver leaderboard_repo._source_table)
        sums = ", ".join(f"SUM({c}) AS {c}" for c in PLAYER_COUNT_COLUMNS)
        poss_join = f"""
            LEFT JOIN (
                SELECT {keys}, {sums}, SUM(offensive_possessions) AS poss
                FROM main_marts.fact_player_games
                WHERE has_possessions
                GROUP BY {keys}
            ) p USING ({keys})
        """

    def scaled(col: str) -> str:
        if per == "per_game":
            return f"t.{col} * 1.0 / NULLIF(t.games, 0)"
        if per == "per_36":
            return f"t.{col} * 2160.0 / NULLIF(t.seconds, 0)"
        if per == "per_100":
            return f"p.{col} * 100.0 / NULLIF(p.poss, 0)"
        return f"t.{col}"

    minutes = "t.seconds / 60.0 / NULLIF(t.games, 0)" if per == "per_game" else "t.seconds / 60.0"
    select_stats = ",\n".join(
        [f"{scaled(c)} AS {c}" for c in PLAYER_COUNT_COLUMNS]
        + [f"t.{c} AS {c}" for c in PLAYER_RATE_COLUMNS + PLAYER_RAW_COLUMNS]
    )
    allowed = set(PLAYER_COUNT_COLUMNS + PLAYER_RATE_COLUMNS + PLAYER_RAW_COLUMNS + ["games", "minutes"])
    order_by = _sort(page.sort, allowed, "points")

    sql = f"""
        SELECT * FROM (
            SELECT
                t.player_id, trim(t.player_name) AS name, t.player_game_role AS position,
                t.team_id, t.team_name, t.club_id, t.club_name,
                t.edition_id, e.season_name AS edition_name,
                t.competition_id, c.competition_name, t.competition_phase,
                t.games, t.games_started,
                {minutes} AS minutes,
                {select_stats}
            FROM main_marts.agg_player_totals t
            {poss_join}
            {_CONTEXT_JOINS}
            {where_sql}
        )
        ORDER BY {order_by}, player_id
        {pagination_sql(page)}
    """
    cur.execute(sql, fb.params)
    rows = cursor_to_dicts(cur)
    cur.execute(f"SELECT COUNT(*) FROM main_marts.agg_player_totals t {where_sql}", fb.params)
    return rows, scalar(cur) or 0


def team_stats(
    cur: duckdb.DuckDBPyConnection,
    filters: CompetitionFilters,
    per: str,
    page: PageParams,
) -> tuple[list[dict], int]:
    fb = SQLFilterBuilder(table_alias="t")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    fb.add("club_id", filters.club_id)
    fb.add("team_id", filters.team_id)
    where_sql = fb.where_sql()

    def scaled(col: str) -> str:
        if per == "per_game":
            # el marcador está en todos los partidos; el resto del boxscore falta en algunos
            # partidos antiguos, así que su media va sobre los partidos con boxscore
            games = "t.games" if col in ("points", "opponent_points") else "t.games_with_boxscore"
            return f"t.{col} * 1.0 / NULLIF({games}, 0)"
        if per == "per_100":
            # por partido escalado al ritmo medio de los partidos con posesiones: exacto en
            # temporadas con play-by-play completo, aproximado en las demás
            return f"t.{col} * 100.0 / NULLIF(t.games * t.possessions_per_game, 0)"
        return f"t.{col}"

    select_stats = ",\n".join(
        [f"{scaled(c)} AS {c}" for c in TEAM_COUNT_COLUMNS]
        + [f"t.{c} AS {c}" for c in TEAM_RATE_COLUMNS + TEAM_RAW_COLUMNS]
    )
    allowed = set(TEAM_COUNT_COLUMNS + TEAM_RATE_COLUMNS + TEAM_RAW_COLUMNS + ["games", "wins", "losses"])
    order_by = _sort(page.sort, allowed, "wins")

    cur.execute(
        f"""
        SELECT * FROM (
            SELECT
                t.team_id, tm.full_name AS name, tm.abbr, tm.logo,
                t.club_id, t.club_name,
                t.edition_id, e.season_name AS edition_name,
                t.competition_id, c.competition_name, t.competition_phase,
                t.games, t.wins, t.losses,
                {select_stats}
            FROM main_marts.agg_team_totals t
            LEFT JOIN (
                SELECT team_id, any_value(full_name) AS full_name, any_value(abbr) AS abbr, any_value(logo) AS logo
                FROM main_marts.dim_teams GROUP BY team_id
            ) tm ON tm.team_id = t.team_id
            {_CONTEXT_JOINS}
            {where_sql}
        )
        ORDER BY {order_by}, team_id
        {pagination_sql(page)}
        """,
        fb.params,
    )
    rows = cursor_to_dicts(cur)
    cur.execute(f"SELECT COUNT(*) FROM main_marts.agg_team_totals t {where_sql}", fb.params)
    return rows, scalar(cur) or 0
