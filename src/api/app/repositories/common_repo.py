"""
Ayudantes compartidos, necesarios por dos huecos reales del esquema:

1. No existe una tabla maestra de jugador (dim_players). La identidad de
   jugador vive en dim_rosters, que es POR EDICIÓN+EQUIPO. Cuando tenemos
   contexto de edición (una fila de agg_player_totals, fact_player_games...)
   hacemos JOIN directo por (player_id, edition_id, team_id). Cuando NO lo
   tenemos (listado/búsqueda de jugadores, "ficha básica" de un player_id
   suelto), usamos la fila de roster más reciente como proxy de "actual".

2. fact_lineups / agg_lineup_combinations solo traen player_ids (array),
   sin nombres. Resolver un array -> nombres en SQL puro es frágil; lo
   hacemos aquí con una query batch sencilla y la reutilizamos desde
   cualquier servicio que necesite pintar quintetos.
"""

from __future__ import annotations

import duckdb

from app.core.serialization import cursor_to_dicts

_DISPLAY_NAME_SQL = (
    # trim: algunos nombres vienen del feed con espacios delante (" Alex Antetokounmpo")
    "trim(COALESCE(NULLIF(trim(player_nickname), ''), player_first_name || ' ' || player_last_name))"
)


def player_names_batch(
    cur: duckdb.DuckDBPyConnection,
    player_ids: list[int],
    edition_id: int | None = None,
) -> dict[int, str]:
    """
    Nombre para cada player_id. Si se da edition_id, usa el roster exacto de
    esa edición (más preciso: refleja el nombre/equipo de ese momento). Si
    no, usa la fila de roster más reciente por jugador como proxy de actual.
    """
    ids = list(dict.fromkeys(player_ids))  # dedup preservando orden
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)

    if edition_id is not None:
        cur.execute(
            f"""
            SELECT player_id, {_DISPLAY_NAME_SQL} AS name
            FROM main_marts.dim_rosters
            WHERE player_id IN ({placeholders}) AND edition_id = ?
            """,
            [*ids, edition_id],
        )
    else:
        cur.execute(
            f"""
            SELECT player_id, name FROM (
                SELECT player_id, {_DISPLAY_NAME_SQL} AS name,
                       ROW_NUMBER() OVER (
                           PARTITION BY player_id ORDER BY edition_id DESC
                       ) AS rn
                FROM main_marts.dim_rosters
                WHERE player_id IN ({placeholders})
            ) ranked
            WHERE rn = 1
            """,
            ids,
        )
    rows = cursor_to_dicts(cur)
    result = {r["player_id"]: r["name"] for r in rows}

    # Si se pidió una edición concreta y algún jugador no estaba en su roster
    # (p.ej. lineups que abarcan varias ediciones), usamos su nombre más reciente.
    missing = [i for i in ids if i not in result]
    if edition_id is not None and missing:
        result.update(player_names_batch(cur, missing, None))
    return result


def match_info_batch(cur: duckdb.DuckDBPyConnection, match_ids: list[int]) -> dict[int, dict]:
    """Datos básicos de varios partidos (fecha, temporada, competición, jornada, equipos y marcador)."""
    ids = [i for i in dict.fromkeys(match_ids) if i is not None]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    cur.execute(
        f"""
        SELECT
            m.match_id, m.match_start_time AS date, e.season_name, c.competition_name, m.round_number,
            m.home_team_id, ht.full_name AS home_team_name, m.away_team_id, at_.full_name AS away_team_name,
            m.home_score, m.away_score
        FROM main_marts.dim_matches m
        LEFT JOIN main_marts.dim_editions e ON e.edition_id = m.edition_id
        LEFT JOIN main_marts.dim_competitions c ON c.competition_id = m.competition_id
        LEFT JOIN (SELECT team_id, any_value(full_name) AS full_name FROM main_marts.dim_teams GROUP BY team_id) ht
            ON ht.team_id = m.home_team_id
        LEFT JOIN (SELECT team_id, any_value(full_name) AS full_name FROM main_marts.dim_teams GROUP BY team_id) at_
            ON at_.team_id = m.away_team_id
        WHERE m.match_id IN ({placeholders})
        """,
        ids,
    )
    return {r["match_id"]: r for r in cursor_to_dicts(cur)}


def match_context_for_team(info: dict | None, team_id: int | None) -> dict:
    """Campos de contexto de un partido vistos desde un equipo: rival, marcador y resultado."""
    if not info:
        return {}
    home = info["home_team_id"] == team_id
    own, opp = (info["home_score"], info["away_score"]) if home else (info["away_score"], info["home_score"])
    date = info.get("date")
    return {
        "date": date[:10] if isinstance(date, str) else (date.isoformat()[:10] if date else None),
        "season": info.get("season_name"),
        "competition": info.get("competition_name"),
        "round": info.get("round_number"),
        "team": {"id": team_id, "name": info["home_team_name"] if home else info["away_team_name"]},
        "opponent": {
            "id": info["away_team_id"] if home else info["home_team_id"],
            "name": info["away_team_name"] if home else info["home_team_name"],
        },
        "score": f"{own}-{opp}" if own is not None and opp is not None else None,
        "result": None if own is None or opp is None else ("V" if own > opp else "D"),
    }
