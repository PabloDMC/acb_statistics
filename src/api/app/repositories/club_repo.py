"""
Repositorio de Clubs. No existe una tabla dim_clubs (ver notas en el
README): "club" aquí es solo un club_id que agrupa team_id a través de
ediciones. Esta es la pieza que resuelve la pregunta de "dame todos los
team_id históricos de este club_id" — la base para filtrar cualquier otro
endpoint de equipo por club en vez de por team_id de una temporada suelta.
"""

from __future__ import annotations

import duckdb

from app.core.serialization import cursor_to_dicts


def list_teams_for_club(cur: duckdb.DuckDBPyConnection, club_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT DISTINCT
            tm.team_id, tm.full_name AS team_name,
            tm.edition_id, e.season_name AS edition_name,
            tm.competition_id, c.competition_name
        FROM main_marts.dim_teams tm
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = tm.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = tm.competition_id
        WHERE tm.club_id = ?
        ORDER BY tm.edition_id DESC
        """,
        [club_id],
    )
    return cursor_to_dicts(cur)
