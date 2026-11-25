from __future__ import annotations

import streamlit as st

import filters
import leaders

sel = filters.current()
if not sel:
    st.stop()

st.title("Líderes y récords")
st.caption("Rankings: los mejores en cada estadística, récords en un partido, clutch y parejas asistente-anotador. "
           "La tabla completa de todos los jugadores, ordenable por cualquier columna, está en Temporada › "
           "Estadísticas de jugadores.")
scope = st.segmented_control(
    "Ámbito", options=["season", "historic"], default="season", key="lead_scope",
    format_func=lambda s: f"Temporada {sel['edition_name']}" if s == "season" else "Histórico de la liga",
) or "season"

if scope == "season":
    flt = filters.api_filters(sel)
    st.caption(f"{sel['competition_name']} {sel['edition_name']}" + (f" · {sel['competition_phase']}" if sel["competition_phase"] else ""))
else:
    flt = {"competition_id": sel["competition_id"], "competition_phase": sel["competition_phase"]}
    st.caption(f"{sel['competition_name']}" + (f" · {sel['competition_phase']}" if sel["competition_phase"] else "")
               + ", todas las temporadas desde 1983-84 (clutch y parejas, desde 2016-17). La competición y la fase se "
               "eligen en la barra lateral.")

leaders.render(flt, key=f"lead_{scope}", historic=scope == "historic")
