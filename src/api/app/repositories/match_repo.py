"""
Repositorio de Matches — ajustado al esquema real.

Huecos reales:
- dim_matches NO tiene competition_phase ni club_id: solo se puede filtrar
  por edition_id/competition_id a este nivel.
- No hay un campo "venue" único: hay home_arena/away_arena. Se usa
  home_arena como venue (el partido se juega en el pabellón del local).
- No hay columna "date": se usa match_start_time (timestamp completo).
- fact_shots usa is_made/shot_value/shot_zone_basic, no made/value/zone/
  shot_type.
- fact_lineups no trae nombres de jugador: se resuelven en el servicio.
"""

from __future__ import annotations

import duckdb

from app.core.exceptions import ResourceNotFoundError
from app.core.serialization import cursor_to_dicts, row_to_dict, scalar
from app.repositories.base import SQLFilterBuilder, pagination_sql, resolve_sort
from app.schemas.common import CompetitionFilters, PageParams

_MATCH_SELECT = """
    SELECT
        m.match_id AS id,
        m.edition_id, e.season_name AS edition_name,
        m.competition_id, c.competition_name,
        ph.competition_phase,
        m.match_start_time AS date,
        m.home_team_id, ht.full_name AS home_team_name,
        m.away_team_id, at_.full_name AS away_team_name,
        m.home_score, m.away_score,
        m.home_arena AS venue
    FROM main_marts.dim_matches m
    LEFT JOIN main_marts.dim_editions e ON e.edition_id = m.edition_id
    LEFT JOIN main_marts.dim_competitions c ON c.competition_id = m.competition_id
    LEFT JOIN (
        SELECT match_id, ANY_VALUE(competition_phase) AS competition_phase
        FROM main_marts.fact_team_games GROUP BY match_id
    ) ph ON ph.match_id = m.match_id
    LEFT JOIN main_marts.dim_teams ht ON ht.team_id = m.home_team_id AND ht.edition_id = m.edition_id AND ht.competition_id = m.competition_id
    LEFT JOIN main_marts.dim_teams at_ ON at_.team_id = m.away_team_id AND at_.edition_id = m.edition_id AND at_.competition_id = m.competition_id
"""


def get_match(cur: duckdb.DuckDBPyConnection, match_id: int) -> dict | None:
    cur.execute(f"{_MATCH_SELECT} WHERE m.match_id = ?", [match_id])
    return row_to_dict(cur)


def require_match(cur: duckdb.DuckDBPyConnection, match_id: int) -> dict:
    match = get_match(cur, match_id)
    if match is None:
        raise ResourceNotFoundError("match", match_id)
    return match


def list_matches(
    cur: duckdb.DuckDBPyConnection, filters: CompetitionFilters, page: PageParams
) -> tuple[list[dict], int]:
    # dim_matches no tiene competition_phase ni club_id/team_id genérico:
    # solo soportamos edition_id/competition_id a este nivel.
    fb = SQLFilterBuilder(table_alias="m")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    if filters.competition_phase is not None:
        fb.clauses.append("ph.competition_phase = ?")
        fb.params.append(filters.competition_phase)
    where_sql = fb.where_sql()

    sort_col, direction = resolve_sort(page.sort, {"date", "id"}, default="date")
    sort_col_sql = {"date": "m.match_start_time", "id": "m.match_id"}[sort_col]

    cur.execute(
        f"{_MATCH_SELECT} {where_sql} ORDER BY {sort_col_sql} {direction} {pagination_sql(page)}",
        fb.params,
    )
    items = cursor_to_dicts(cur)

    cur.execute(
        f"""SELECT COUNT(*) FROM main_marts.dim_matches m
        LEFT JOIN (SELECT match_id, ANY_VALUE(competition_phase) AS competition_phase
                   FROM main_marts.fact_team_games GROUP BY match_id) ph ON ph.match_id = m.match_id
        {where_sql}""",
        fb.params,
    )
    total = scalar(cur) or 0
    return items, total


def get_shots(
    cur: duckdb.DuckDBPyConnection,
    match_id: int,
    team_id: int | None,
    player_id: int | None,
    clutch_only: bool = False,
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="s")
    fb.clauses.append("s.match_id = ?")
    fb.params.append(match_id)
    fb.add("team_id", team_id)
    fb.add("player_id", player_id)
    if clutch_only:
        fb.clauses.append("s.is_clutch = TRUE")

    cur.execute(
        f"""
        SELECT
            s.player_id,
            s.x, s.y,
            s.is_made AS made,
            s.shot_value AS value,
            s.shot_zone_basic AS zone,
            s.is_clutch,
            s.quarter,
            s.seconds_remaining
        FROM main_marts.fact_shots s
        {fb.where_sql()}
        ORDER BY s.quarter, s.seconds_remaining DESC
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)


def get_lineup_stints(cur: duckdb.DuckDBPyConnection, match_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            l.team_id, l.team_full_name,
            l.quarter,
            l.start_time,
            l.end_time,
            l.player_ids,
            l.team_points,
            l.opp_points,
            l.plus_minus,
            l.offensive_possessions,
            l.defensive_possessions
        FROM main_marts.fact_lineups l
        WHERE l.match_id = ?
        ORDER BY l.quarter, l.start_time
        """,
        [match_id],
    )
    return cursor_to_dicts(cur)
