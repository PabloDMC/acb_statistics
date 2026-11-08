"""
Repositorio de Leaderboards.

scope:
  - "season" (por defecto): cada fila de agg_player_totals / agg_team_totals
    es una entrada (jugador+edición+competición+fase). Si no filtras por
    edition_id, esto YA te da "mejores marcas históricas en una temporada"
    (el equivalente a "single-season leaders" de Basketball-Reference).
  - "career": agrega (SUM, o fórmula ponderada para ratios) todas las filas
    que cumplan los demás filtros, agrupando solo por jugador/equipo. Es
    "total o promedio de toda la carrera dentro de ese filtro".

per:
  - "total" (por defecto): el valor crudo (o la suma, en career).
  - "per_game": dividido por partidos jugados.
  - "per_100_poss": dividido por posesiones, x100.
  - "per_40_min": dividido por segundos jugados, x40x60.
  per_* solo es válido para métricas "contables" (ver schemas/leaderboard.py);
  para pct/ratings no tiene sentido (ya son una tasa) y el service lo rechaza
  antes de llegar aquí.
"""

from __future__ import annotations

import duckdb

from app.core.serialization import cursor_to_dicts
from app.repositories.base import SQLFilterBuilder, pagination_sql
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.leaderboard import (
    PLAYER_CAREER_RATE_FORMULAS,
    PLAYER_LEADERBOARD_METRICS,
    TEAM_CAREER_RATE_FORMULAS,
    TEAM_LEADERBOARD_METRICS,
)

_PER_DIVISORS = {
    # nombre -> (columna divisor, factor en el numerador, factor extra)
    "per_game": ("t.games", 1.0, 1.0),
    # por 100 posesiones de ATAQUE del equipo (con el jugador en pista, en su caso);
    # `possessions` es ataque + defensa y dejaba el valor a la mitad
    "per_100_poss": ("t.offensive_possessions", 100.0, 1.0),
    "per_40_min": ("t.seconds", 1.0, 40.0 * 60.0),
}


def _source_table(table: str, column: str, per: str | None) -> str:
    """
    Tabla de la que sale el leaderboard. Para per_100_poss, en vez del agregado se suman
    solo los partidos que tienen posesiones (has_possessions): en temporadas con
    play-by-play incompleto, dividir el total de la temporada entre las posesiones de solo
    algunos partidos inflaba el valor (p. ej. 2017-18).
    """
    if per != "per_100_poss":
        return f"main_marts.{table}"
    if table == "agg_player_totals":
        fact, keys, games = "fact_player_games", "player_id, team_id", "COUNT(*) FILTER (WHERE seconds > 0)"
    else:
        fact, keys, games = "fact_team_games", "team_id", "COUNT(*)"
    return f"""(
        SELECT edition_id, competition_id, competition_phase, {keys},
               {games} AS games,
               SUM({column}) AS {column},
               SUM(offensive_possessions) AS offensive_possessions
        FROM main_marts.{fact}
        WHERE has_possessions
        GROUP BY edition_id, competition_id, competition_phase, {keys}
    )"""


def player_leaderboard(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    filters: CompetitionFilters,
    page: PageParams,
    min_games: int,
    scope: str,
    per: str | None,
) -> list[dict]:
    column = PLAYER_LEADERBOARD_METRICS[metric]  # validado antes en el service

    fb = SQLFilterBuilder(table_alias="t")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    fb.add("team_id", filters.team_id)
    if filters.club_id is not None:
        fb.clauses.append("tm.club_id = ?")
        fb.params.append(filters.club_id)

    base_join = """
        LEFT JOIN main_marts.dim_teams tm ON tm.team_id = t.team_id AND tm.edition_id = t.edition_id
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = t.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = t.competition_id
    """

    if scope == "season":
        raw_expr = f"t.{column}"
        if per and per != "total":
            divisor_col, num_factor, extra_factor = _PER_DIVISORS[per]
            value_expr = f"(t.{column} * {num_factor} / NULLIF({divisor_col}, 0) * {extra_factor})"
        else:
            value_expr = raw_expr

        fb.clauses.append("t.games >= ?")
        fb.params.append(min_games)
        fb.clauses.append(f"({value_expr}) IS NOT NULL")

        cur.execute(
            f"""
            SELECT
                ROW_NUMBER() OVER (ORDER BY {value_expr} DESC) AS rank,
                t.player_id,
                t.team_id, tm.full_name AS team_name, tm.club_id, tm.club_name,
                t.edition_id, e.season_name AS edition_name,
                t.competition_id, c.competition_name,
                t.competition_phase,
                {value_expr} AS value
            FROM {_source_table('agg_player_totals', column, per)} t
            {base_join}
            {fb.where_sql()}
            ORDER BY value DESC
            {pagination_sql(page)}
            """,
            fb.params,
        )
        return cursor_to_dicts(cur)

    # scope == "career": agregamos a través de todas las filas que matcheen filtros.
    agg_expr = PLAYER_CAREER_RATE_FORMULAS.get(metric)
    if agg_expr is None:
        agg_expr = f"SUM(t.{column})"
        if per and per != "total":
            divisor_col, num_factor, extra_factor = _PER_DIVISORS[per]
            agg_expr = f"(SUM(t.{column}) * {num_factor} / NULLIF(SUM({divisor_col.split('.')[1]}), 0) * {extra_factor})"

    cur.execute(
        f"""
        SELECT * FROM (
            SELECT
                t.player_id,
                ANY_VALUE(t.team_id) AS team_id, ANY_VALUE(tm.full_name) AS team_name,
                ANY_VALUE(tm.club_id) AS club_id, ANY_VALUE(tm.club_name) AS club_name,
                SUM(t.games) AS total_games,
                {agg_expr} AS value
            FROM {_source_table('agg_player_totals', column, per)} t
            {base_join}
            {fb.where_sql()}
            GROUP BY t.player_id
            HAVING SUM(t.games) >= ? AND value IS NOT NULL
        )
        ORDER BY value DESC
        {pagination_sql(page)}
        """,
        [*fb.params, min_games],
    )
    rows = cursor_to_dicts(cur)
    for i, row in enumerate(rows, start=1 + page.offset):
        row["rank"] = i
        row["edition_id"] = None
        row["edition_name"] = "Carrera"
        row["competition_id"] = filters.competition_id
        row["competition_name"] = None
        row["competition_phase"] = filters.competition_phase
    return rows


def team_leaderboard(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    filters: CompetitionFilters,
    page: PageParams,
    scope: str,
    per: str | None,
) -> list[dict]:
    column = TEAM_LEADERBOARD_METRICS[metric]

    fb = SQLFilterBuilder(table_alias="t")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    if filters.club_id is not None:
        fb.clauses.append("tm.club_id = ?")
        fb.params.append(filters.club_id)

    base_join = """
        LEFT JOIN main_marts.dim_teams tm ON tm.team_id = t.team_id AND tm.edition_id = t.edition_id
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = t.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = t.competition_id
    """

    if scope == "season":
        if per and per != "total":
            divisor_col, num_factor, extra_factor = _PER_DIVISORS[per]
            value_expr = f"(t.{column} * {num_factor} / NULLIF({divisor_col}, 0) * {extra_factor})"
        else:
            value_expr = f"t.{column}"
        fb.clauses.append(f"({value_expr}) IS NOT NULL")

        cur.execute(
            f"""
            SELECT
                ROW_NUMBER() OVER (ORDER BY {value_expr} DESC) AS rank,
                t.team_id, tm.full_name AS team_name, tm.club_id, tm.club_name,
                t.edition_id, e.season_name AS edition_name,
                t.competition_id, c.competition_name,
                t.competition_phase,
                {value_expr} AS value
            FROM {_source_table('agg_team_totals', column, per)} t
            {base_join}
            {fb.where_sql()}
            ORDER BY value DESC
            {pagination_sql(page)}
            """,
            fb.params,
        )
        return cursor_to_dicts(cur)

    agg_expr = TEAM_CAREER_RATE_FORMULAS.get(metric)
    if agg_expr is None:
        agg_expr = f"SUM(t.{column})"
        if per and per != "total":
            divisor_col, num_factor, extra_factor = _PER_DIVISORS[per]
            agg_expr = f"(SUM(t.{column}) * {num_factor} / NULLIF(SUM({divisor_col.split('.')[1]}), 0) * {extra_factor})"

    cur.execute(
        f"""
        SELECT * FROM (
            -- Carrera = por CLUB: team_id es una participación concreta (un club en una
            -- temporada y competición), así que agrupar por él no sumaba nada. Se muestra
            -- el equipo (nombre comercial) más reciente del club.
            SELECT
                tm.club_id, ANY_VALUE(tm.club_name) AS club_name,
                arg_max(t.team_id, t.edition_id) AS team_id,
                arg_max(tm.full_name, t.edition_id) AS team_name,
                {agg_expr} AS value
            FROM {_source_table('agg_team_totals', column, per)} t
            {base_join}
            {fb.where_sql()}
            GROUP BY tm.club_id
            HAVING value IS NOT NULL
        )
        ORDER BY value DESC
        {pagination_sql(page)}
        """,
        fb.params,
    )
    rows = cursor_to_dicts(cur)
    for i, row in enumerate(rows, start=1 + page.offset):
        row["rank"] = i
        row["edition_id"] = None
        row["edition_name"] = "Carrera"
        row["competition_id"] = filters.competition_id
        row["competition_name"] = None
        row["competition_phase"] = filters.competition_phase
    return rows


# ---------------------------------------------------------------------------
# Leaderboards de tiro: por zona y/o solo en clutch.
#
# Camino rápido (sin clutch): agg_player_shooting_zones ya está pre-agregada
# por player+edición+zona, así que es una simple consulta GROUP BY player_id.
# Camino clutch: agg_player_shooting_zones NO distingue clutch (es un dato
# que solo existe a nivel de lanzamiento individual), así que para
# clutch_only=True agregamos directamente sobre fact_shots.
# ---------------------------------------------------------------------------

def shooting_leaderboard(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    zone: str | None,
    clutch_only: bool,
    filters: CompetitionFilters,
    min_attempts: int,
    page: PageParams,
) -> list[dict]:
    if not clutch_only:
        return _shooting_leaderboard_from_agg(cur, metric, zone, filters, min_attempts, page)
    return _shooting_leaderboard_from_shots(cur, metric, zone, filters, min_attempts, page)


def _shooting_leaderboard_from_agg(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    zone: str | None,
    filters: CompetitionFilters,
    min_attempts: int,
    page: PageParams,
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="z")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    fb.add("club_id", filters.club_id)
    fb.add("team_id", filters.team_id)
    if zone is not None:
        fb.clauses.append("z.shot_zone_basic = ?")
        fb.params.append(zone)

    value_col = {
        "made": "SUM(z.field_goals_made)",
        "attempted": "SUM(z.field_goals_attempted)",
        "pct": "SUM(z.field_goals_made) * 1.0 / NULLIF(SUM(z.field_goals_attempted), 0)",
        "frequency": "AVG(z.field_goal_frequency)",  # ya es un ratio por fila; promedio simple es razonable
    }[metric]

    cur.execute(
        f"""
        SELECT x.*, e.season_name AS edition_name, c.competition_name FROM (
            SELECT
                z.player_id,
                ANY_VALUE(tm.full_name) AS team_name, ANY_VALUE(z.team_id) AS team_id,
                ANY_VALUE(z.club_id) AS club_id, ANY_VALUE(tm.club_name) AS club_name,
                -- contexto: la edición/competición/fase si todas las filas son de una sola
                CASE WHEN COUNT(DISTINCT z.edition_id) = 1 THEN ANY_VALUE(z.edition_id) END AS edition_id,
                CASE WHEN COUNT(DISTINCT z.competition_id) = 1 THEN ANY_VALUE(z.competition_id) END AS competition_id,
                CASE WHEN COUNT(DISTINCT z.competition_phase) = 1 THEN ANY_VALUE(z.competition_phase) END AS competition_phase,
                SUM(z.field_goals_made) AS made,
                SUM(z.field_goals_attempted) AS attempted,
                {value_col} AS value
            FROM main_marts.agg_player_shooting_zones z
            LEFT JOIN main_marts.dim_teams tm ON tm.team_id = z.team_id AND tm.edition_id = z.edition_id
            {fb.where_sql()}
            GROUP BY z.player_id
            HAVING SUM(z.field_goals_attempted) >= ? AND value IS NOT NULL
        ) x
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = x.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = x.competition_id
        ORDER BY value DESC
        {pagination_sql(page)}
        """,
        [*fb.params, min_attempts],
    )
    rows = cursor_to_dicts(cur)
    for i, row in enumerate(rows, start=1 + page.offset):
        row["rank"] = i
    return rows


def _shooting_leaderboard_from_shots(
    cur: duckdb.DuckDBPyConnection,
    metric: str,
    zone: str | None,
    filters: CompetitionFilters,
    min_attempts: int,
    page: PageParams,
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="s")
    fb.clauses.append("s.is_clutch = TRUE")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    fb.add("club_id", filters.club_id)
    fb.add("team_id", filters.team_id)
    if zone is not None:
        fb.clauses.append("s.shot_zone_basic = ?")
        fb.params.append(zone)

    if metric == "frequency":
        raise ValueError("frequency no está disponible para clutch_only=True todavía")

    value_col = {
        "made": "SUM(CASE WHEN s.is_made THEN 1 ELSE 0 END)",
        "attempted": "COUNT(*)",
        "pct": "SUM(CASE WHEN s.is_made THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(*), 0)",
    }[metric]

    cur.execute(
        f"""
        SELECT x.*, e.season_name AS edition_name, c.competition_name FROM (
            SELECT
                s.player_id,
                ANY_VALUE(tm.full_name) AS team_name, ANY_VALUE(s.team_id) AS team_id,
                ANY_VALUE(s.club_id) AS club_id, ANY_VALUE(tm.club_name) AS club_name,
                -- contexto: la edición/competición/fase si todas las filas son de una sola
                CASE WHEN COUNT(DISTINCT s.edition_id) = 1 THEN ANY_VALUE(s.edition_id) END AS edition_id,
                CASE WHEN COUNT(DISTINCT s.competition_id) = 1 THEN ANY_VALUE(s.competition_id) END AS competition_id,
                CASE WHEN COUNT(DISTINCT s.competition_phase) = 1 THEN ANY_VALUE(s.competition_phase) END AS competition_phase,
                SUM(CASE WHEN s.is_made THEN 1 ELSE 0 END) AS made,
                COUNT(*) AS attempted,
                {value_col} AS value
            FROM main_marts.fact_shots s
            LEFT JOIN main_marts.dim_teams tm ON tm.team_id = s.team_id AND tm.edition_id = s.edition_id
            {fb.where_sql()}
            GROUP BY s.player_id
            HAVING COUNT(*) >= ? AND value IS NOT NULL
        ) x
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = x.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = x.competition_id
        ORDER BY value DESC
        {pagination_sql(page)}
        """,
        [*fb.params, min_attempts],
    )
    rows = cursor_to_dicts(cur)
    for i, row in enumerate(rows, start=1 + page.offset):
        row["rank"] = i
    return rows


def available_shot_zones(cur: duckdb.DuckDBPyConnection) -> list[str]:
    cur.execute(
        "SELECT DISTINCT shot_zone_basic FROM main_marts.agg_player_shooting_zones "
        "WHERE shot_zone_basic IS NOT NULL ORDER BY 1"
    )
    return [row[0] for row in cur.fetchall()]
