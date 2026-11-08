"""
Repositorio de Teams — ajustado al esquema real.

Huecos reales que afectan aquí:
- dim_teams es POR EDICIÓN (team_id + edition_id): para "info básica" de un
  team_id suelto usamos la fila más reciente, igual que con jugadores.
- club_id y club_name salen de dim_teams; wins/losses vienen ya en
  agg_team_totals, por fase.
- En las respuestas de equipo, `possessions` son las posesiones de ATAQUE
  del equipo (las tablas guardan además ataque + defensa en `possessions`).
- agg_lineup_combinations no trae nombres de jugador ni un id de
  combinación: el id se sintetiza en el servicio a partir de player_ids, y
  los nombres se resuelven con common_repo.player_names_batch.
"""

from __future__ import annotations

import duckdb

from app.core.exceptions import ResourceNotFoundError
from app.core.serialization import cursor_to_dicts, row_to_dict, scalar
from app.repositories.base import SQLFilterBuilder, pagination_sql, resolve_sort
from app.schemas.common import CompetitionFilters, PageParams


def get_basic_info(cur: duckdb.DuckDBPyConnection, team_id: int) -> dict | None:
    cur.execute(
        """
        SELECT team_id AS id, full_name AS name, club_id, club_name
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY team_id ORDER BY edition_id DESC
            ) AS rn
            FROM main_marts.dim_teams
            WHERE team_id = ?
        )
        WHERE rn = 1
        """,
        [team_id],
    )
    return row_to_dict(cur)


def require_basic_info(cur: duckdb.DuckDBPyConnection, team_id: int) -> dict:
    info = get_basic_info(cur, team_id)
    if info is None:
        raise ResourceNotFoundError("team", team_id)
    return info


def list_teams(
    cur: duckdb.DuckDBPyConnection,
    name_query: str | None,
    filters: CompetitionFilters,
    page: PageParams,
) -> tuple[list[dict], int]:
    fb = SQLFilterBuilder(table_alias="tm")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("club_id", filters.club_id)
    fb.add("team_id", filters.team_id)
    if name_query:
        fb.clauses.append("tm.full_name ILIKE ?")
        fb.params.append(f"%{name_query}%")
    where_sql = fb.where_sql()

    sort_col, direction = resolve_sort(page.sort, {"name", "id"}, default="name", default_direction="ASC")
    # Importante: estas columnas se refieren al SELECT exterior (que ya
    # renombró full_name -> name, team_id -> id), no a dim_teams directamente.
    sort_col_sql = {"name": "lower(strip_accents(name))", "id": "id"}[sort_col]

    cur.execute(
        f"""
        SELECT * FROM (
            SELECT
                tm.team_id AS id, tm.full_name AS name, tm.club_id, tm.club_name,
                ROW_NUMBER() OVER (PARTITION BY tm.team_id ORDER BY tm.edition_id DESC) AS rn
            FROM main_marts.dim_teams tm
            {where_sql}
        )
        WHERE rn = 1
        ORDER BY {sort_col_sql} {direction}
        {pagination_sql(page)}
        """,
        fb.params,
    )
    items = cursor_to_dicts(cur)

    cur.execute(f"SELECT COUNT(DISTINCT tm.team_id) FROM main_marts.dim_teams tm {where_sql}", fb.params)
    total = scalar(cur) or 0
    return items, total


def get_totals(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="t")
    fb.clauses.append("t.team_id = ?")
    fb.params.append(team_id)
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    if filters.club_id is not None:
        fb.clauses.append("tm.club_id = ?")
        fb.params.append(filters.club_id)

    cur.execute(
        f"""
        SELECT
            t.edition_id, e.season_name AS edition_name,
            t.competition_id, c.competition_name,
            t.competition_phase,
            t.team_id, tm.full_name AS team_name,
            tm.club_id, tm.club_name,

            t.games AS games_played, t.wins, t.losses,
            t.points AS points_for, t.opponent_points AS points_against,
            t.offensive_possessions AS possessions,
            t.offensive_rating, t.defensive_rating, t.net_rating
        FROM main_marts.agg_team_totals t
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = t.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = t.competition_id
        LEFT JOIN main_marts.dim_teams tm ON tm.team_id = t.team_id AND tm.edition_id = t.edition_id AND tm.competition_id = t.competition_id
        {fb.where_sql()}
        ORDER BY t.edition_id DESC
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


def get_game_log(
    cur: duckdb.DuckDBPyConnection,
    team_id: int,
    filters: CompetitionFilters,
    page: PageParams,
) -> tuple[list[dict], int]:
    fb = SQLFilterBuilder(table_alias="g")
    fb.clauses.append("g.team_id = ?")
    fb.params.append(team_id)
    fb.add_competition_filters(filters)  # fact_team_games sí tiene club_id
    where_sql = fb.where_sql()

    sort_col, direction = resolve_sort(
        page.sort, {"match_id", "net_rating", "points"}, default="match_id"
    )

    cur.execute(
        f"""
        SELECT
            g.match_id,
            g.edition_id, e.season_name AS edition_name,
            g.competition_id, c.competition_name,
            g.competition_phase,
            g.is_home,
            CASE WHEN g.points > g.opponent_points THEN 'W' ELSE 'L' END AS result,
            g.opponent_team_id, opp.full_name AS opponent_team_name,
            g.points AS points_for, g.opponent_points AS points_against,
            g.offensive_possessions AS possessions,
            g.offensive_rating, g.defensive_rating, g.net_rating
        FROM main_marts.fact_team_games g
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = g.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = g.competition_id
        LEFT JOIN main_marts.dim_teams opp
            ON opp.team_id = g.opponent_team_id AND opp.edition_id = g.edition_id AND opp.competition_id = g.competition_id
        {where_sql}
        ORDER BY g.{sort_col} {direction}
        {pagination_sql(page)}
        """,
        fb.params,
    )
    items = cursor_to_dicts(cur)

    cur.execute(f"SELECT COUNT(*) FROM main_marts.fact_team_games g {where_sql}", fb.params)
    total = scalar(cur) or 0
    return items, total


def get_lineup_combinations(
    cur: duckdb.DuckDBPyConnection,
    team_id: int,
    filters: CompetitionFilters,
    combination_size: int | None,
    page: PageParams,
) -> tuple[list[dict], int]:
    fb = SQLFilterBuilder(table_alias="l")
    fb.clauses.append("l.team_id = ?")
    fb.params.append(team_id)
    if combination_size is not None:
        fb.clauses.append("l.player_count = ?")
        fb.params.append(combination_size)
    fb.add_competition_filters(filters)  # agg_lineup_combinations sí tiene club_id
    where_sql = fb.where_sql()

    sort_col, direction = resolve_sort(
        page.sort, {"minutes", "net_rating", "possessions"}, default="minutes"
    )

    cur.execute(
        f"""
        SELECT
            l.player_ids,
            l.player_count AS combination_size,
            l.minutes,
            l.possessions,
            l.offensive_rating,
            l.defensive_rating,
            l.net_rating,
            l.plus_minus
        FROM main_marts.agg_lineup_combinations l
        {where_sql}
        ORDER BY l.{sort_col} {direction}
        {pagination_sql(page)}
        """,
        fb.params,
    )
    items = cursor_to_dicts(cur)

    cur.execute(f"SELECT COUNT(*) FROM main_marts.agg_lineup_combinations l {where_sql}", fb.params)
    total = scalar(cur) or 0
    return items, total


# ---------------------------------------------------------------------------
# Game highs de equipo
# ---------------------------------------------------------------------------

_TEAM_GAME_HIGH_STATS: dict[str, str] = {
    "points": "points",
    "opponent_points": "opponent_points",
    "rebounds": "total_rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "three_pointers_made": "three_pointers_made",
    "field_goals_made": "field_goals_made",
    "net_rating": "net_rating",
}


def get_game_highs(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters
) -> dict:
    fb = SQLFilterBuilder(table_alias="g")
    fb.clauses.append("g.team_id = ?")
    fb.params.append(team_id)
    fb.add_competition_filters(filters)

    select_parts = [
        f"MAX(g.{col}) AS {name}_value, arg_max(g.match_id, g.{col}) AS {name}_match_id"
        for name, col in _TEAM_GAME_HIGH_STATS.items()
    ]
    select_parts.append(
        "MAX(g.points - g.opponent_points) AS margin_value, "
        "arg_max(g.match_id, g.points - g.opponent_points) AS margin_match_id"
    )
    cur.execute(
        f"SELECT {', '.join(select_parts)} FROM main_marts.fact_team_games g {fb.where_sql()}",
        fb.params,
    )
    return row_to_dict(cur) or {}
