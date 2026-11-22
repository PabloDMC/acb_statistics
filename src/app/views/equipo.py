from __future__ import annotations

import streamlit as st

import api
import components
import nav

team_id = nav.read("equipo", "id")
if team_id is None:
    st.title("Equipo")
    st.write("Busca un equipo o elige uno en la clasificación:")
    components.search_box(key="team_page_search")
    st.stop()

rows = (api.get("/stats/teams", team_id=team_id, per="total") or {}).get("items", [])
if not rows:
    st.error(f"No hay datos del equipo {team_id}.")
    st.stop()

first = rows[0]
record = ", ".join(
    f"{r['context']['competition']['name']} {r['context']['competition_phase']}: {r['wins']}-{r['losses']}"
    for r in rows
)
components.entity_header(
    first["club_team"]["team"]["name"],
    f"{first['context']['edition']['name']} · {record}",
    first.get("logo"),
)

st.info("Plantilla, calendario, four factors, cartas de tiro, quintetos y rotaciones: paso 3 de la hoja de ruta.")
