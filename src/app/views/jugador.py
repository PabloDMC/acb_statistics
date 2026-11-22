from __future__ import annotations

import streamlit as st

import api
import components
import nav

player_id = nav.read("jugador", "id")
if player_id is None:
    st.title("Jugador")
    st.write("Busca un jugador:")
    components.search_box(key="player_page_search")
    st.stop()

info = api.get(f"/players/{player_id}")
if not info:
    st.error(f"No existe el jugador {player_id}.")
    st.stop()

parts = [
    info.get("position"),
    (info.get("current_team") or {}).get("name"),
    f"#{info['shirt_number']}" if info.get("shirt_number") else None,
]
first, last = info.get("first_season") or {}, info.get("last_season") or {}
if first.get("name"):
    parts.append(f"{info.get('seasons')} temporadas ({first['name']} – {last.get('name')})")
components.entity_header(
    info["name"],
    " · ".join(p for p in parts if p),
    info.get("headshot_no_background_url") or info.get("headshot_image_url"),
)

st.info("Totales, avanzadas, partido a partido, tiro, impacto y quintetos: paso 3 de la hoja de ruta.")
