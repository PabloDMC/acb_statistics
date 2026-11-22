from __future__ import annotations

import streamlit as st

import api
import nav

match_id = nav.read("partido", "id")
if match_id is None:
    st.title("Partido")
    st.write("Abre un partido desde el calendario de un equipo o la página de un jugador.")
    st.stop()

m = api.get(f"/matches/{match_id}")
if not m:
    st.error(f"No existe el partido {match_id}.")
    st.stop()

ctx = m["context"]
st.caption(
    f"{ctx['competition']['name']} {ctx['edition']['name']}"
    + (f" · Jornada {m['round']}" if m.get("round") else "")
    + (f" · {m['date'][:10]}" if m.get("date") else "")
)
home, score, away = st.columns([3, 2, 3])
with home:
    if m.get("home_team_logo"):
        st.image(m["home_team_logo"], width=72)
    st.subheader(m["home_team"]["name"])
with score:
    st.markdown(
        f"<div style='text-align:center;white-space:nowrap;font-size:2.6rem;font-weight:700;"
        f"padding-top:1.2rem'>{m['home_score']} – {m['away_score']}</div>",
        unsafe_allow_html=True,
    )
with away:
    if m.get("away_team_logo"):
        st.image(m["away_team_logo"], width=72)
    st.subheader(m["away_team"]["name"])

extra = [m.get("venue"), f"{m['attendance']:,} espectadores".replace(",", ".") if m.get("attendance") else None]
st.caption(" · ".join(e for e in extra if e))

st.info("Boxscore, jugada a jugada, evolución del marcador, rotaciones y carta de tiro: paso 3 de la hoja de ruta.")
