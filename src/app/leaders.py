"""
Bloque de líderes y récords reutilizable (página Líderes y sección Líderes del equipo):
generales, clutch (totales), récords en un partido y parejas asistente-anotador.
`flt` son los filtros de la API (edition_id, competition_id, competition_phase, team_id, club_id).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import api
import components
import nav

GENERAL = [
    ("points", "Puntos"), ("rebounds", "Rebotes"), ("assists", "Asistencias"),
    ("steals", "Robos"), ("blocks", "Tapones"), ("three_pointers_made", "Triples"),
    ("rating", "Valoración"), ("double_doubles", "Dobles-dobles"),
]
PER_LABELS = {"total": "Totales", "per_game": "Por partido", "per_40_min": "Por 40 min", "per_100_poss": "Por 100 posesiones"}

CLUTCH = {
    "points": "Puntos", "field_goals_made": "Tiros de campo anotados", "field_goals_pct": "% tiros de campo",
    "three_pointers_made": "Triples", "three_pointers_pct": "% triples", "free_throws_made": "Tiros libres anotados",
    "free_throws_pct": "% tiros libres", "total_rebounds": "Rebotes", "assists": "Asistencias",
    "steals": "Robos", "blocks": "Tapones", "turnovers": "Pérdidas",
}
PLAYER_RECORDS = {
    "points": "Puntos", "total_rebounds": "Rebotes", "assists": "Asistencias", "steals": "Robos",
    "blocks": "Tapones", "three_pointers_made": "Triples", "field_goals_made": "Tiros de campo",
    "free_throws_made": "Tiros libres", "rating": "Valoración", "plus_minus": "+/-", "seconds": "Minutos",
}
TEAM_RECORDS = {
    "points": "Puntos anotados", "opponent_points": "Puntos recibidos", "margin": "Diferencia",
    "three_pointers_made": "Triples", "assists": "Asistencias", "total_rebounds": "Rebotes",
    "steals": "Robos", "blocks": "Tapones", "rating": "Valoración", "offensive_rating": "Rating ofensivo",
}
KINDS = {"all": "Todas", "2P": "Canastas de 2", "3P": "Triples", "FT": "Tiros libres"}


def _goto_from(df: pd.DataFrame, row, page: str, col: str = "_id") -> None:
    if row is not None and pd.notna(df.iloc[row][col]):
        nav.goto(page, id=int(df.iloc[row][col]))


def render(flt: dict, key: str, historic: bool) -> None:
    kind = components.sections(["Generales", "Clutch", "Récords en un partido", "Parejas"], key=f"{key}_kind")
    if kind == "Generales":
        _general(flt, key, historic)
    elif kind == "Clutch":
        _clutch(flt, key)
    elif kind == "Récords en un partido":
        _records(flt, key)
    else:
        _pairs(flt, key)


def _general(flt: dict, key: str, historic: bool) -> None:
    c1, c2 = st.columns([3, 1])
    per = c1.segmented_control("Escala", options=list(PER_LABELS), format_func=PER_LABELS.get,
                               default="total" if historic else "per_game", key=f"{key}_per") or "per_game"
    min_games = c2.number_input("Mín. partidos", min_value=0, value=50 if historic else 5, step=5, key=f"{key}_min")
    scope = "career" if historic else "season"
    cols = st.columns(4)
    for i, (metric, label) in enumerate(GENERAL):
        if i == 4:
            cols = st.columns(4)
        with cols[i % 4]:
            st.markdown(f"**{label}**")
            lb = api.get("/leaderboards/players", metric=metric, per=per, min_games=min_games, limit=10,
                         scope=scope, **flt) or []
            if not lb:
                st.caption("Sin datos.")
                continue
            df = pd.DataFrame([
                {"Jugador": e["player"]["name"], label: e["value"], "_id": e["player"]["id"]}
                for e in lb
            ])
            row = components.selectable_table(
                df.drop(columns="_id"), key=f"{key}_g_{metric}",
                column_config={label: st.column_config.NumberColumn(label, format="%d" if per == "total" else "%.1f")},
            )
            _goto_from(df, row, "jugador")
    if historic:
        st.caption("Histórico: suma de toda la carrera dentro de los filtros (todas las temporadas desde 2016-17).")


def _clutch(flt: dict, key: str) -> None:
    c1, c2 = st.columns([3, 1])
    metric = c1.selectbox("Estadística", options=list(CLUTCH), format_func=CLUTCH.get, key=f"{key}_c_metric")
    min_att = c2.number_input("Mín. intentos (para %)", min_value=0, value=20, step=5, key=f"{key}_c_min")
    lb = api.get("/leaderboards/clutch", metric=metric, min_attempts=min_att, limit=25, **flt) or []
    if not lb:
        st.info("Sin datos de clutch.")
        return
    is_pct = metric.endswith("_pct")
    df = pd.DataFrame([
        {
            "#": e["rank"],
            CLUTCH[metric]: (100 * e["value"]) if is_pct and e["value"] is not None else e["value"],
            "Jugador": e["player"]["name"],
            "Equipo": (e.get("team") or {}).get("name"),
            "PJ": e["games"],
            "Pts": e["stats"].get("points"),
            "TC": f"{e['stats'].get('field_goals_made')}/{e['stats'].get('field_goals_attempted')}",
            "T3": f"{e['stats'].get('three_pointers_made')}/{e['stats'].get('three_pointers_attempted')}",
            "TL": f"{e['stats'].get('free_throws_made')}/{e['stats'].get('free_throws_attempted')}",
            "Reb": e["stats"].get("total_rebounds"),
            "Ast": e["stats"].get("assists"),
            "Pér": e["stats"].get("turnovers"),
            "_id": e["player"]["id"],
        }
        for e in lb
    ])
    row = components.selectable_table(
        df.drop(columns="_id"), key=f"{key}_c_table",
        column_config={CLUTCH[metric]: st.column_config.NumberColumn(CLUTCH[metric], format="%.1f" if is_pct else "%d")},
    )
    st.caption("Totales en clutch: últimos 5 minutos del último cuarto y prórrogas con el marcador a 5 puntos o menos. "
               "Solo partidos con jugada a jugada. PJ = partidos con alguna acción en clutch.")
    _goto_from(df, row, "jugador")


def _records(flt: dict, key: str) -> None:
    c1, c2 = st.columns([1, 2])
    target = c1.segmented_control("De", options=["players", "teams"], default="players", key=f"{key}_r_target",
                                  format_func=lambda t: "Jugadores" if t == "players" else "Equipos") or "players"
    options = PLAYER_RECORDS if target == "players" else TEAM_RECORDS
    metric = c2.selectbox("Estadística", options=list(options), format_func=options.get, key=f"{key}_r_metric_{target}")
    recs = api.get("/leaderboards/game-records", target=target, metric=metric, limit=25, **flt) or []
    if not recs:
        st.info("Sin datos.")
        return
    df = pd.DataFrame([
        {
            "#": r["rank"],
            options[metric]: r["value"],
            **({"Jugador": r["player"]["name"]} if target == "players" else {}),
            "Equipo": r["team"]["name"],
            "Rival": (r.get("opponent") or {}).get("name"),
            "Res": r.get("result"),
            "Marcador": r.get("score"),
            "Fecha": r.get("date"),
            "Temporada": r.get("season"),
            "Competición": r.get("competition"),
            "_id": r["match_id"],
        }
        for r in recs
    ])
    row = components.selectable_table(
        df.drop(columns="_id"), key=f"{key}_r_table",
        column_config={options[metric]: st.column_config.NumberColumn(options[metric], format="%.1f" if metric in ("seconds", "offensive_rating") else "%d")},
    )
    st.caption("Pulsa una fila para abrir el partido.")
    _goto_from(df, row, "partido")


def _pairs(flt: dict, key: str) -> None:
    c1, c2 = st.columns([3, 2])
    kind = c1.segmented_control("Tipo de canasta", options=list(KINDS), format_func=KINDS.get, default="all",
                                key=f"{key}_p_kind") or "all"
    sort = c2.segmented_control("Ordenar por", options=["plays", "points"], default="plays", key=f"{key}_p_sort",
                                format_func=lambda s: "Canastas asistidas" if s == "plays" else "Puntos") or "plays"
    pairs = api.get("/leaderboards/assist-pairs", kind=kind, sort=sort, limit=25, **flt) or []
    if not pairs:
        st.info("Sin datos (hace falta la jugada a jugada).")
        return
    df = pd.DataFrame([
        {
            "#": p["rank"],
            "Asiste": p["assister"]["name"],
            "Anota": p["scorer"]["name"],
            "Equipo": (p.get("team") or {}).get("name"),
            "Asistencias": p["assisted_plays"],
            "Puntos": p["points"],
            "De 2": p["two_pointers"],
            "Triples": p["three_pointers"],
            "A tiros libres": p["free_throw_trips"],
        }
        for p in pairs
    ])
    st.dataframe(df, hide_index=True, use_container_width=True, height=35 * len(df) + 38)
    st.caption("Totales. Una asistencia que acaba en tiros libres cuenta como una (los puntos son los libres anotados). "
               "Solo partidos con jugada a jugada.")
