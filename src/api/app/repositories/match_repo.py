"""
Repositorio de Matches — ajustado al esquema real.

Huecos reales:
- dim_matches no tiene competition_phase ni club_id: la fase sale de fact_team_games
  y el club de dim_teams (local o visitante).
- No hay un campo "venue" único: hay home_arena/away_arena. Se usa
  home_arena como venue (el partido se juega en el pabellón del local).
- No hay columna "date": se usa match_start_time (timestamp completo).
- fact_shots usa is_made/shot_value/shot_zone_basic, no made/value/zone/
  shot_type.
- fact_lineups no trae nombres de jugador: se resuelven en el servicio.
- En fact_lineups, start_time/end_time son segundos RESTANTES del cuarto
  (cuenta atrás), así que el orden cronológico es start_time descendente.
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
        m.home_arena AS venue,
        m.round_number, m.attendance,
        m.home_head_coach, m.away_head_coach, m.referees,
        ht.logo AS home_team_logo, at_.logo AS away_team_logo
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
    cur: duckdb.DuckDBPyConnection,
    filters: CompetitionFilters,
    page: PageParams,
    round_number: int | None = None,
    opponent_team_id: int | None = None,
    opponent_club_id: int | None = None,
) -> tuple[list[dict], int]:
    fb = SQLFilterBuilder(table_alias="m")
    fb.add("edition_id", filters.edition_id)
    fb.add("competition_id", filters.competition_id)
    if filters.competition_phase is not None:
        fb.clauses.append("ph.competition_phase = ?")
        fb.params.append(filters.competition_phase)
    # team_id / club_id: partidos en los que el equipo (o un equipo del club) juega de local o visitante
    if filters.team_id is not None:
        fb.clauses.append("(m.home_team_id = ? OR m.away_team_id = ?)")
        fb.params.extend([filters.team_id, filters.team_id])
    if filters.club_id is not None:
        fb.clauses.append("(ht.club_id = ? OR at_.club_id = ?)")
        fb.params.extend([filters.club_id, filters.club_id])
    # rival: junto con team_id/club_id da los enfrentamientos directos entre los dos
    if opponent_team_id is not None:
        fb.clauses.append("(m.home_team_id = ? OR m.away_team_id = ?)")
        fb.params.extend([opponent_team_id, opponent_team_id])
    if opponent_club_id is not None:
        fb.clauses.append("(ht.club_id = ? OR at_.club_id = ?)")
        fb.params.extend([opponent_club_id, opponent_club_id])
    fb.add("round_number", round_number)
    where_sql = fb.where_sql()

    sort_col, direction = resolve_sort(page.sort, {"date", "id"}, default="date")
    sort_col_sql = {"date": "m.match_start_time", "id": "m.match_id"}[sort_col]

    cur.execute(
        f"{_MATCH_SELECT} {where_sql} ORDER BY {sort_col_sql} {direction} {pagination_sql(page)}",
        fb.params,
    )
    items = cursor_to_dicts(cur)

    cur.execute(f"SELECT COUNT(*) FROM ({_MATCH_SELECT} {where_sql})", fb.params)
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

    # tiros de campo: fact_shots trae también los tiros libres (zona 14, en 0,0), que no
    # van en una carta de tiro
    fb.clauses.append("s.zone_id <> 14")
    cur.execute(
        f"""
        SELECT
            s.player_id,
            s.x, s.y,
            s.is_made AS made,
            s.shot_value AS value,
            s.team_id,
            s.zone_id,
            s.shot_zone_basic AS zone,
            s.shot_zone_area AS area,
            s.shot_zone_range AS range,
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
        ORDER BY l.quarter, l.start_time DESC, l.stint_id, l.is_home DESC
        """,
        [match_id],
    )
    return cursor_to_dicts(cur)


# ---------------------------------------------------------------------------
# Boxscore y jugada a jugada
# ---------------------------------------------------------------------------

def get_boxscore_players(cur: duckdb.DuckDBPyConnection, match_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            g.team_id, g.player_id, trim(g.player_name) AS player_name,
            r.player_shirt_number AS shirt_number,
            g.is_starter, g.seconds, g.play_time,
            g.points,
            g.field_goals_made, g.field_goals_attempted,
            g.two_pointers_made, g.two_pointers_attempted,
            g.three_pointers_made, g.three_pointers_attempted,
            g.free_throws_made, g.free_throws_attempted,
            g.off_rebounds, g.def_rebounds, g.total_rebounds,
            g.assists, g.steals, g.turnovers, g.blocks, g.received_blocks,
            g.dunks, g.personal_fouls, g.fouls_drawn, g.plus_minus, g.rating
        FROM main_marts.fact_player_games g
        LEFT JOIN (
            SELECT player_id, team_id, edition_id, any_value(player_shirt_number) AS player_shirt_number
            FROM main_marts.dim_rosters GROUP BY player_id, team_id, edition_id
        ) r ON r.player_id = g.player_id AND r.team_id = g.team_id AND r.edition_id = g.edition_id
        WHERE g.match_id = ?
        ORDER BY g.team_id, g.is_starter DESC, g.seconds DESC, g.player_id
        """,
        [match_id],
    )
    return cursor_to_dicts(cur)


def get_boxscore_teams(cur: duckdb.DuckDBPyConnection, match_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
            team_id, is_home, points, opponent_points, seconds,
            field_goals_made, field_goals_attempted, field_goals_pct,
            two_pointers_made, two_pointers_attempted, two_pointers_pct,
            three_pointers_made, three_pointers_attempted, three_pointers_pct,
            free_throws_made, free_throws_attempted, free_throws_pct,
            off_rebounds, def_rebounds, total_rebounds, team_off_rebounds, team_def_rebounds,
            assists, steals, turnovers, team_turnovers, blocks, received_blocks, dunks,
            personal_fouls, fouls_drawn, rating,
            offensive_possessions, offensive_rating, defensive_rating, net_rating
        FROM main_marts.fact_team_games
        WHERE match_id = ?
        """,
        [match_id],
    )
    return cursor_to_dicts(cur)


def get_quarter_scores(cur: duckdb.DuckDBPyConnection, match_id: int) -> list[dict]:
    """Marcador acumulado al final de cada cuarto (de la jugada a jugada)."""
    cur.execute(
        """
        SELECT quarter, max(score_home) AS home, max(score_away) AS away
        FROM main_marts.fact_play_by_play
        WHERE match_id = ?
        GROUP BY quarter
        ORDER BY quarter
        """,
        [match_id],
    )
    return cursor_to_dicts(cur)


def get_play_by_play(
    cur: duckdb.DuckDBPyConnection, match_id: int, quarter: int | None, include_system: bool
) -> list[dict]:
    fb = SQLFilterBuilder(table_alias="p")
    fb.clauses.append("p.match_id = ?")
    fb.params.append(match_id)
    fb.add("quarter", quarter)
    if not include_system:
        fb.clauses.append("coalesce(p.play_category, '') NOT IN ('System', 'IR')")
        fb.clauses.append("NOT p.is_synthetic")
    cur.execute(
        f"""
        SELECT
            p.event_idx, p.quarter, p.seconds_remaining,
            p.play_type_id, p.play_name, p.play_category, p.play_sub_category,
            p.team_id, p.player_id, p.points,
            p.score_home, p.score_away,
            p.is_clutch, p.possession_id, p.offense_team_id, p.event_kind
        FROM main_marts.fact_play_by_play p
        {fb.where_sql()}
        ORDER BY p.event_idx
        """,
        fb.params,
    )
    return cursor_to_dicts(cur)
