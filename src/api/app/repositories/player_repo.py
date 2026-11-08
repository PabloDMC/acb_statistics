"""
Repositorio de Players — ajustado al esquema REAL (volcado con
scripts/inspect_schema.py).

Huecos reales del esquema que afectan a este fichero:
- No hay dim_players: la "ficha" de un player_id se resuelve tomando la
  fila de dim_rosters más reciente para ese jugador (no hay bio -
  nacimiento/nacionalidad/posición/altura- en ningún sitio del warehouse).
- agg_player_totals y agg_team_totals NO tienen club_id propio (solo
  team_id): para poder filtrar/mostrar club_id hay que unir con dim_teams.
- El nombre de club sale de dim_teams.club_name (dim_clubs en dbt).
"""

from __future__ import annotations

import duckdb

from app.core.exceptions import ResourceNotFoundError
from app.core.serialization import cursor_to_dicts, row_to_dict, scalar
from app.repositories.base import SQLFilterBuilder, pagination_sql, resolve_sort
from app.schemas.common import CompetitionFilters, PageParams

_DISPLAY_NAME_SQL = (
    # trim: algunos nombres vienen del feed con espacios delante (" Alex Antetokounmpo")
    "trim(COALESCE(NULLIF(trim(player_nickname), ''), player_first_name || ' ' || player_last_name))"
)

# ---------------------------------------------------------------------------
# Info básica (dim_rosters, fila más reciente por jugador)
# ---------------------------------------------------------------------------

def get_basic_info(cur: duckdb.DuckDBPyConnection, player_id: int) -> dict | None:
    cur.execute(
        f"""
        SELECT player_id AS id, {_DISPLAY_NAME_SQL} AS name,
               player_shirt_number AS shirt_number,
               player_headshot_image_url AS headshot_image_url
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY player_id ORDER BY edition_id DESC
            ) AS rn
            FROM main_marts.dim_rosters
            WHERE player_id = ?
        )
        WHERE rn = 1
        """,
        [player_id],
    )
    return row_to_dict(cur)


def require_basic_info(cur: duckdb.DuckDBPyConnection, player_id: int) -> dict:
    info = get_basic_info(cur, player_id)
    if info is None:
        raise ResourceNotFoundError("player", player_id)
    return info


def list_players(
    cur: duckdb.DuckDBPyConnection,
    name_query: str | None,
    filters: CompetitionFilters,
    page: PageParams,
) -> tuple[list[dict], int]:
    """
    Si vienen filtros de contexto (edition_id/team_id/club_id...), lista
    jugadores que estuvieron en ESE contexto exacto. Si no hay filtros,
    lista la fila más reciente por jugador (proxy de "plantilla actual").
    """
    fb = SQLFilterBuilder(table_alias="r")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("club_id", filters.club_id)
    fb.add("team_id", filters.team_id)
    if name_query:
        fb.clauses.append(
            f"({_DISPLAY_NAME_SQL.replace('player_', 'r.player_')}) ILIKE ?"
        )
        fb.params.append(f"%{name_query}%")
    where_sql = fb.where_sql()

    sort_col, direction = resolve_sort(page.sort, {"name", "id"}, default="name", default_direction="ASC")
    # orden alfabético sin distinguir mayúsculas ni acentos (si no, "Ángel" sale detrás de la Z)
    sort_col_sql = {"name": "lower(strip_accents(r.name))", "id": "r.id"}[sort_col]

    # Primero se elige la fila más reciente por jugador (solo dim_rosters) y después se une
    # dim_teams para esas filas: antes se unía para todas las filas del histórico.
    cur.execute(
        f"""
        WITH r AS (
            SELECT
                r.player_id AS id,
                {_DISPLAY_NAME_SQL.replace('player_', 'r.player_')} AS name,
                r.team_id, r.edition_id, r.competition_id, r.club_id
            FROM main_marts.dim_rosters r
            {where_sql}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY r.player_id ORDER BY r.edition_id DESC) = 1
        )
        SELECT
            r.id, r.name,
            r.team_id AS current_team_id, tm.full_name AS current_team_name,
            r.club_id AS current_club_id, tm.club_name AS current_club_name
        FROM r
        LEFT JOIN main_marts.dim_teams tm
            ON tm.team_id = r.team_id AND tm.edition_id = r.edition_id AND tm.competition_id = r.competition_id
        ORDER BY {sort_col_sql} {direction}, r.id
        {pagination_sql(page)}
        """,
        fb.params,
    )
    items = cursor_to_dicts(cur)

    cur.execute(
        f"""
        SELECT COUNT(DISTINCT r.player_id)
        FROM main_marts.dim_rosters r
        {where_sql}
        """,
        fb.params,
    )
    total = scalar(cur) or 0
    return items, total


# ---------------------------------------------------------------------------
# Totales (agg_player_totals) — sin club_id propio: unimos dim_teams
# ---------------------------------------------------------------------------

_TOTALS_SELECT = """
    SELECT
        t.edition_id, e.season_name AS edition_name,
        t.competition_id, c.competition_name,
        t.competition_phase,
        t.team_id, tm.full_name AS team_name,
        tm.club_id, tm.club_name,

        t.games AS games_played, t.games_started, t.seconds,
        t.points, t.assists, t.total_rebounds AS rebounds,
        t.steals, t.turnovers, t.blocks,
        t.personal_fouls, t.fouls_drawn, t.rating,

        t.field_goals_made, t.field_goals_attempted, t.field_goals_pct,
        t.two_pointers_made, t.two_pointers_attempted, t.two_pointers_pct,
        t.three_pointers_made, t.three_pointers_attempted, t.three_pointers_pct,
        t.free_throws_made, t.free_throws_attempted, t.free_throws_pct,

        t.effective_field_goals_pct, t.true_shooting_pct,
        t.is_double_double AS double_doubles, t.is_triple_double AS triple_doubles
    FROM main_marts.agg_player_totals t
    LEFT JOIN main_marts.dim_editions e ON e.edition_id = t.edition_id
    LEFT JOIN main_marts.dim_competitions c ON c.competition_id = t.competition_id
    LEFT JOIN main_marts.dim_teams tm ON tm.team_id = t.team_id AND tm.edition_id = t.edition_id AND tm.competition_id = t.competition_id
"""


def get_totals(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="t")
    fb.clauses.append("t.player_id = ?")
    fb.params.append(player_id)
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    fb.add("team_id", filters.team_id)
    if filters.club_id is not None:
        fb.clauses.append("tm.club_id = ?")
        fb.params.append(filters.club_id)

    cur.execute(f"{_TOTALS_SELECT} {fb.where_sql()} ORDER BY t.edition_id DESC", fb.params)
    return cursor_to_dicts(cur)


# ---------------------------------------------------------------------------
# Partido a partido (fact_player_games) — ya trae opponent_team_id/is_home
# ---------------------------------------------------------------------------

def get_game_log(
    cur: duckdb.DuckDBPyConnection,
    player_id: int,
    filters: CompetitionFilters,
    page: PageParams,
    include_dnp: bool = False,
) -> tuple[list[dict], int]:
    fb = SQLFilterBuilder(table_alias="g")
    fb.clauses.append("g.player_id = ?")
    fb.params.append(player_id)
    fb.add_competition_filters(filters)  # g tiene club_id y team_id nativos
    if not include_dnp:
        # mismo criterio que los partidos jugados de agg_player_totals
        fb.clauses.append("g.seconds > 0")
    where_sql = fb.where_sql()

    sort_col, direction = resolve_sort(
        page.sort, {"points", "rating", "match_id", "plus_minus"}, default="match_id"
    )

    cur.execute(
        f"""
        SELECT
            g.match_id,
            g.edition_id, e.season_name AS edition_name,
            g.competition_id, c.competition_name,
            g.competition_phase,
            g.is_home,
            g.opponent_team_id, opp.full_name AS opponent_team_name,

            g.seconds, g.points, g.assists, g.total_rebounds AS rebounds,
            g.steals, g.turnovers, g.blocks, g.plus_minus, g.rating,

            g.field_goals_made, g.field_goals_attempted, g.field_goals_pct,
            g.three_pointers_made, g.three_pointers_attempted, g.three_pointers_pct,
            g.free_throws_made, g.free_throws_attempted, g.free_throws_pct
        FROM main_marts.fact_player_games g
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

    cur.execute(f"SELECT COUNT(*) FROM main_marts.fact_player_games g {where_sql}", fb.params)
    total = scalar(cur) or 0
    return items, total


# ---------------------------------------------------------------------------
# Shooting (agg_player_shooting + agg_player_shooting_zones) — sí traen club_id
# ---------------------------------------------------------------------------

def get_shooting_profile(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="s")
    fb.clauses.append("s.player_id = ?")
    fb.params.append(player_id)
    fb.add_competition_filters(filters)

    cur.execute(
        f"""
        SELECT
            s.edition_id, e.season_name AS edition_name,
            s.competition_id, c.competition_name,
            s.competition_phase,
            s.team_id, tm.full_name AS team_name,
            s.club_id, tm.club_name,

            s.field_goals_made, s.field_goals_attempted, s.field_goals_pct,
            s.two_pointers_made, s.two_pointers_attempted, s.two_pointers_pct,
            s.three_pointers_made, s.three_pointers_attempted, s.three_pointers_pct,
            s.free_throws_made, s.free_throws_attempted, s.free_throws_pct,
            s.dunks_made, s.dunks_attempted, s.dunks_pct,

            s.assisted_field_goals_made, s.unassisted_field_goals_made,
            s.assisted_field_goals_pct,
            s.assisted_two_pointers_made, s.assisted_three_pointers_made,
            s.assisted_dunks, s.unassisted_dunks,
            s.and_ones
        FROM main_marts.agg_player_shooting s
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = s.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = s.competition_id
        LEFT JOIN main_marts.dim_teams tm ON tm.team_id = s.team_id AND tm.edition_id = s.edition_id AND tm.competition_id = s.competition_id
        {fb.where_sql()}
        ORDER BY s.edition_id DESC
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


def get_shooting_zones(
    cur: duckdb.DuckDBPyConnection, player_id: int, context: dict
) -> list[dict]:
    """Zonas para EXACTAMENTE el contexto (edición/competición/fase/equipo) de una fila de shooting."""
    fb = SQLFilterBuilder(table_alias="z")
    fb.clauses.append("z.player_id = ?")
    fb.params.append(player_id)
    fb.add("edition_id", context.get("edition_id"))
    fb.add("competition_id", context.get("competition_id"))
    fb.add("competition_phase", context.get("competition_phase"))
    fb.add("team_id", context.get("team_id"))

    cur.execute(
        f"""
        SELECT
            z.shot_zone_basic AS zone,
            z.field_goals_attempted,
            z.field_goals_made,
            z.field_goals_pct,
            z.field_goal_frequency
        FROM main_marts.agg_player_shooting_zones z
        {fb.where_sql()}
        ORDER BY z.field_goal_frequency DESC
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


_ZONE_KEY = ("edition_id", "competition_id", "competition_phase", "team_id")


def get_shooting_zones_batch(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> dict[tuple, list[dict]]:
    """
    Zonas de todas las filas de shooting del jugador en UNA consulta, agrupadas por
    (edition_id, competition_id, competition_phase, team_id). Sustituye a llamar a
    get_shooting_zones por cada fila (N+1: ~40 consultas para un jugador veterano).
    """
    fb = SQLFilterBuilder(table_alias="z")
    fb.clauses.append("z.player_id = ?")
    fb.params.append(player_id)
    fb.add_competition_filters(filters)

    cur.execute(
        f"""
        SELECT
            z.edition_id, z.competition_id, z.competition_phase, z.team_id,
            z.shot_zone_basic AS zone,
            z.field_goals_attempted,
            z.field_goals_made,
            z.field_goals_pct,
            z.field_goal_frequency
        FROM main_marts.agg_player_shooting_zones z
        {fb.where_sql()}
        ORDER BY z.field_goal_frequency DESC
        """,
        fb.params,
    )
    zones: dict[tuple, list[dict]] = {}
    for row in cursor_to_dicts(cur):
        key = tuple(row.pop(k) for k in _ZONE_KEY)
        zones.setdefault(key, []).append(row)
    return zones


# ---------------------------------------------------------------------------
# Impacto: On-court / On-off — todo vive en agg_player_totals
# ---------------------------------------------------------------------------

def get_impact(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="t")
    fb.clauses.append("t.player_id = ?")
    fb.params.append(player_id)
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    fb.add("competition_phase", filters.competition_phase)
    fb.add("team_id", filters.team_id)

    cur.execute(
        f"""
        SELECT
            t.edition_id, e.season_name AS edition_name,
            t.competition_id, c.competition_name,
            t.competition_phase,

            -- `possessions` es ataque + defensa: 100 posesiones de partido son 200 de esas.
            -- Diferencial de quinteto (team_points - opp_points), no el +/- del boxscore: este
            -- incluye partidos sin play-by-play y no casa con las posesiones.
            ((t.team_points - t.opp_points) * 200.0 / NULLIF(t.possessions, 0)) AS on_court_plus_minus_per_100,
            t.offensive_rating AS on_court_offensive_rating,
            t.defensive_rating AS on_court_defensive_rating,
            t.net_rating AS on_court_net_rating,
            t.off_net_rating AS off_court_net_rating,
            t.onoff_net_rating AS on_off_net_rating,
            t.possessions AS possessions_on_court
        FROM main_marts.agg_player_totals t
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = t.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = t.competition_id
        {fb.where_sql()}
        ORDER BY t.edition_id DESC
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


# ---------------------------------------------------------------------------
# Lineups en los que participa (agg_lineup_combinations, player_count = 5)
# ---------------------------------------------------------------------------

def get_lineup_participations(
    cur: duckdb.DuckDBPyConnection,
    player_id: int,
    filters: CompetitionFilters,
    limit: int = 10,
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="l")
    fb.clauses.append("list_contains(l.player_ids, ?)")
    fb.params.append(player_id)
    fb.clauses.append("l.player_count = 5")
    fb.add_competition_filters(filters)

    cur.execute(
        f"""
        SELECT
            l.player_ids,
            l.edition_id,
            l.minutes,
            l.possessions,
            l.offensive_rating,
            l.defensive_rating,
            l.net_rating,
            l.plus_minus
        FROM main_marts.agg_lineup_combinations l
        {fb.where_sql()}
        ORDER BY l.minutes DESC
        LIMIT {int(limit)}
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


# ---------------------------------------------------------------------------
# Lanzamientos individuales del jugador (fact_shots) — para shot charts de
# temporada completa, a diferencia de match_repo.get_shots que es por partido.
# ---------------------------------------------------------------------------

def get_shots(
    cur: duckdb.DuckDBPyConnection,
    player_id: int,
    filters: CompetitionFilters,
    clutch_only: bool = False,
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="s")
    fb.clauses.append("s.player_id = ?")
    fb.params.append(player_id)
    fb.add_competition_filters(filters)  # fact_shots tiene club_id y team_id nativos
    if clutch_only:
        fb.clauses.append("s.is_clutch = TRUE")

    cur.execute(
        f"""
        SELECT
            s.match_id,
            s.x, s.y,
            s.is_made AS made,
            s.shot_value AS value,
            s.shot_zone_basic AS zone,
            s.is_clutch,
            s.quarter,
            s.seconds_remaining
        FROM main_marts.fact_shots s
        {fb.where_sql()}
        ORDER BY s.match_id, s.quarter, s.seconds_remaining DESC
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


# ---------------------------------------------------------------------------
# Game highs (marcas de mejor partido) — arg_max trae a la vez el valor
# máximo y el match_id donde ocurrió, en una sola pasada sobre fact_player_games.
# ---------------------------------------------------------------------------

_GAME_HIGH_STATS: dict[str, str] = {
    "points": "points",
    "rebounds": "total_rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "three_pointers_made": "three_pointers_made",
    "field_goals_made": "field_goals_made",
    "free_throws_made": "free_throws_made",
    "plus_minus": "plus_minus",
    "rating": "rating",
    "seconds_played": "seconds",
}


def get_game_highs(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> dict:
    fb = SQLFilterBuilder(table_alias="g")
    fb.clauses.append("g.player_id = ?")
    fb.params.append(player_id)
    fb.add_competition_filters(filters)

    select_parts = [
        f"MAX(g.{col}) AS {name}_value, arg_max(g.match_id, g.{col}) AS {name}_match_id"
        for name, col in _GAME_HIGH_STATS.items()
    ]
    cur.execute(
        f"SELECT {', '.join(select_parts)} FROM main_marts.fact_player_games g {fb.where_sql()}",
        fb.params,
    )
    return row_to_dict(cur) or {}
