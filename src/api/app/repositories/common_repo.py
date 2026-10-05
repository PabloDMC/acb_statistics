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
    "COALESCE(NULLIF(player_nickname, ''), "
    "player_first_name || ' ' || player_last_name)"
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
