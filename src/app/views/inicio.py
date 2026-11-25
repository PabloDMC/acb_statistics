from __future__ import annotations

import pandas as pd
import streamlit as st

import api
import components
import filters
import nav

sel = filters.current()

st.title("ACB Statistics")
st.caption("Estadísticas de la Liga Endesa, la Copa del Rey y la Supercopa desde 1983-84. Jugada a jugada, "
           "quintetos, rotaciones y cartas de tiro, desde 2016-17.")

components.search_box(key="home_search")

if not sel:
    st.stop()

left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader(f"Clasificación {sel['edition_name']}")
    standings = api.get("/standings", edition_id=sel["edition_id"], competition_id=1, competition_phase="LR")
    if standings:
        df = pd.DataFrame([
            {
                "Pos": r["position"],
                "Logo": r["logo"],
                "Equipo": r["team"]["name"],
                "V": r["wins"],
                "D": r["losses"],
                "Dif": r["point_diff"],
                "Racha": r["streak"],
                "_id": r["team"]["id"],
            }
            for r in standings["rows"]
        ])
        row = components.selectable_table(
            df.drop(columns="_id"),
            key="home_standings",
            column_config={"Logo": st.column_config.ImageColumn("", width="small")},
            height=35 * len(df) + 38,
        )
        if not standings.get("official", True):
            st.caption("Esa temporada la fase regular se jugó en grupos o en varias fases: es el balance de cada "
                       "equipo, no la clasificación oficial.")
        if row is not None:
            nav.goto("equipo", id=int(df.iloc[row]["_id"]))
    else:
        st.info("Sin clasificación de liga regular para esta temporada.")
    if st.button("Ver la temporada completa", icon=":material/leaderboard:"):
        nav.goto("temporada")

with right:
    st.subheader("Máximos anotadores")
    leaders = api.get(
        "/leaderboards/players",
        metric="points", per="per_game", min_games=5, limit=10,
        **filters.api_filters(sel),
    ) or []
    if leaders:
        df = pd.DataFrame([
            {
                "Jugador": e["player"]["name"],
                "Equipo": e["club_team"]["team"]["name"],
                "PJ": e.get("games"),
                "Puntos": round(e["value"], 1),
                "_id": e["player"]["id"],
            }
            for e in leaders
        ])
        row = components.selectable_table(df.drop(columns="_id"), key="home_leaders")
        if row is not None:
            nav.goto("jugador", id=int(df.iloc[row]["_id"]))
