"""
Repositorio de temporada: catálogo de ediciones, partidos para la clasificación, medias de tiro
de la liga y búsqueda. La clasificación se ordena en el servicio (los desempates oficiales no
se expresan bien en SQL).
"""

from __future__ import annotations

import duckdb

from app.core.serialization import cursor_to_dicts


def list_editions(cur: duckdb.DuckDBPyConnection) -> list[dict]:
    cur.execute(
        """
        SELECT
            m.edition_id,
            any_value(e.season_name) AS edition_name,
            any_value(e.season_start_year) AS start_year,
            m.competition_id,
            any_value(c.competition_name) AS competition_name,
            m.round_type AS phase,
            count(*) AS matches,
            min(m.match_start_time) AS first_date,
            max(m.match_start_time) AS last_date
        FROM main_marts.dim_matches m
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = m.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = m.competition_id
        GROUP BY m.edition_id, m.competition_id, m.round_type
        ORDER BY m.edition_id DESC, m.competition_id, first_date
        """
    )
    return cursor_to_dicts(cur)


def standings_games(
    cur: duckdb.DuckDBPyConnection,
    edition_id: int,
    competition_id: int,
    competition_phase: str,
) -> list[dict]:
    """Partidos ya jugados de la fase, una fila por equipo y partido, con su jornada."""
    cur.execute(
        """
        SELECT
            g.match_id,
            g.team_id,
            g.opponent_team_id,
            g.is_home,
            g.points,
            g.opponent_points,
            m.round_number,
            m.match_start_time
        FROM main_marts.fact_team_games g
        JOIN main_marts.dim_matches m ON m.match_id = g.match_id
        WHERE g.edition_id = ?
          AND g.competition_id = ?
          AND g.competition_phase = ?
          AND g.points IS NOT NULL
          AND g.opponent_points IS NOT NULL
          AND g.points + g.opponent_points > 0
        ORDER BY m.match_start_time, g.match_id
        """,
        [edition_id, competition_id, competition_phase],
    )
    return cursor_to_dicts(cur)


def teams_info(cur: duckdb.DuckDBPyConnection, team_ids: list[int]) -> dict[int, dict]:
    if not team_ids:
        return {}
    placeholders = ",".join("?" for _ in team_ids)
    cur.execute(
        f"""
        SELECT team_id, any_value(full_name) AS team_name, any_value(abbr) AS abbr,
               any_value(logo) AS logo, any_value(club_id) AS club_id, any_value(club_name) AS club_name
        FROM main_marts.dim_teams
        WHERE team_id IN ({placeholders})
        GROUP BY team_id
        """,
        team_ids,
    )
    return {r["team_id"]: r for r in cursor_to_dicts(cur)}


def context_names(cur: duckdb.DuckDBPyConnection, edition_id: int | None, competition_id: int | None) -> dict:
    cur.execute(
        """
        SELECT
            (SELECT any_value(season_name) FROM main_marts.dim_editions WHERE edition_id = ?) AS edition_name,
            (SELECT any_value(competition_name) FROM main_marts.dim_competitions WHERE competition_id = ?) AS competition_name
        """,
        [edition_id, competition_id],
    )
    row = cursor_to_dicts(cur)
    return row[0] if row else {}


def league_shot_zones(cur: duckdb.DuckDBPyConnection, edition_id: int | None) -> list[dict]:
    where = "WHERE edition_id = ?" if edition_id is not None else ""
    params = [edition_id] if edition_id is not None else []
    cur.execute(
        f"""
        SELECT
            zone_id,
            any_value(shot_zone_basic) AS zone,
            any_value(shot_zone_area) AS area,
            any_value(shot_zone_range) AS range,
            sum(field_goals_attempted) AS attempted,
            sum(field_goals_made) AS made,
            sum(field_goals_made) * 1.0 / NULLIF(sum(field_goals_attempted), 0) AS pct,
            sum(field_goals_attempted) * 1.0
                / NULLIF(sum(sum(field_goals_attempted)) OVER (), 0) AS frequency
        FROM main_marts.agg_league_averages
        {where}
        GROUP BY zone_id
        ORDER BY zone_id
        """,
        params,
    )
    return cursor_to_dicts(cur)


# Búsqueda sin distinguir mayúsculas ni acentos
_NORM = "lower(strip_accents({}))"


def search(cur: duckdb.DuckDBPyConnection, q: str, limit: int) -> dict[str, list[dict]]:
    pattern = f"%{q}%"
    cur.execute(
        f"""
        SELECT p.player_id AS id, trim(p.player_name) AS name,
               t.full_name AS detail, p.latest_team_id AS extra_id
        FROM main_marts.dim_players p
        LEFT JOIN (SELECT team_id, any_value(full_name) AS full_name FROM main_marts.dim_teams GROUP BY team_id) t
            ON t.team_id = p.latest_team_id
        WHERE {_NORM.format('p.player_name')} LIKE {_NORM.format('?')}
        ORDER BY p.last_edition_id DESC, name
        LIMIT ?
        """,
        [pattern, limit],
    )
    players = cursor_to_dicts(cur)

    cur.execute(
        f"""
        SELECT club_id AS id, club_name AS name, latest_team_name AS detail, NULL AS extra_id
        FROM main_marts.dim_clubs
        WHERE {_NORM.format('club_name')} LIKE {_NORM.format('?')}
           OR {_NORM.format('latest_team_name')} LIKE {_NORM.format('?')}
        ORDER BY last_edition_id DESC, name
        LIMIT ?
        """,
        [pattern, pattern, limit],
    )
    clubs = cursor_to_dicts(cur)

    cur.execute(
        f"""
        SELECT t.team_id AS id, t.full_name AS name,
               concat(e.season_name, ' · ', c.competition_name) AS detail, t.club_id AS extra_id
        FROM main_marts.dim_teams t
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = t.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = t.competition_id
        WHERE {_NORM.format('t.full_name')} LIKE {_NORM.format('?')}
        ORDER BY t.edition_id DESC, t.competition_id, name
        LIMIT ?
        """,
        [pattern, limit],
    )
    teams = cursor_to_dicts(cur)
    return {"players": players, "clubs": clubs, "teams": teams}
