from __future__ import annotations

import pandas as pd
import streamlit as st

import api
import components
import filters
import nav

sel = filters.current()
if not sel:
    st.stop()

st.title(f"Temporada {sel['edition_name']}")
st.caption(sel["competition_name"] + (f" · {sel['competition_phase']}" if sel["competition_phase"] else ""))

tab_std, tab_evo, tab_lead, tab_players, tab_teams = st.tabs(
    ["Clasificación", "Evolución", "Líderes", "Jugadores", "Equipos"]
)

with tab_std:
    phase = sel["competition_phase"] or ("LR" if "LR" in sel["phases"] else None)
    standings = api.get(
        "/standings", edition_id=sel["edition_id"], competition_id=sel["competition_id"], competition_phase=phase
    ) if phase else None
    if not standings:
        st.info("No hay clasificación para esta competición y fase.")
    else:
        df = pd.DataFrame([
            {
                "Pos": r["position"],
                "Logo": r["logo"],
                "Equipo": r["team"]["name"],
                "PJ": r["games"],
                "V": r["wins"],
                "D": r["losses"],
                "%V": components.pct(r["win_pct"]),
                "PF": r["points_for"],
                "PC": r["points_against"],
                "Dif": r["point_diff"],
                "Local": f"{r['home_wins']}-{r['home_losses']}",
                "Visitante": f"{r['away_wins']}-{r['away_losses']}",
                "Racha": r["streak"],
                "Últimos 5": r["last5"],
                "_id": r["team"]["id"],
            }
            for r in standings["rows"]
        ])
        row = components.selectable_table(
            df.drop(columns="_id"),
            key="season_standings",
            column_config={"Logo": st.column_config.ImageColumn("", width="small")},
            height=35 * len(df) + 38,
        )
        st.caption(f"Desempate: {standings['tiebreak']}")
        if row is not None:
            nav.goto("equipo", id=int(df.iloc[row]["_id"]))

for tab in (tab_evo, tab_lead, tab_players, tab_teams):
    with tab:
        st.info("En construcción (paso 3 de la hoja de ruta).")
