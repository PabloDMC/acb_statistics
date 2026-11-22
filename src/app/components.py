"""Piezas visuales reutilizables: buscador, cabeceras y formato de tablas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import api
import nav


def search_box(container=None, key: str = "search") -> None:
    """Buscador global de jugadores, clubes y equipos."""
    box = container or st
    # tras saltar a un resultado, el buscador se vacía (solo se puede antes de crear el widget)
    if st.session_state.get("_clear_search"):
        for k in [k for k in st.session_state if str(k).endswith("search")]:
            st.session_state[k] = ""
        st.session_state["_clear_search"] = False
    q = box.text_input("Buscar", placeholder="Jugador, equipo o club", key=key, label_visibility="collapsed")
    if not q or len(q.strip()) < 2:
        return
    res = api.get("/search", q=q.strip(), limit=8)
    if not res:
        return
    hits = (
        [("jugador", h["id"], h["name"], h.get("detail")) for h in res["players"]]
        + [("equipo", h["id"], h["name"], h.get("detail")) for h in res["teams"][:5]]
    )
    if not hits:
        box.caption("Sin resultados.")
        return
    for page, id_, name, detail in hits:
        label = f"{name} · {detail}" if detail else name
        icon = ":material/person:" if page == "jugador" else ":material/groups:"
        if box.button(label, key=f"{key}_{page}_{id_}", icon=icon, use_container_width=True):
            nav.goto(page, id=id_)


def entity_header(title: str, subtitle: str | None = None, image: str | None = None) -> None:
    cols = st.columns([1, 6]) if image else [None, st.container()]
    if image:
        cols[0].image(image, width=96)
    with cols[1]:
        st.title(title)
        if subtitle:
            st.caption(subtitle)


def pct(value: float | None) -> float | None:
    return None if value is None else round(100 * value, 1)


def selectable_table(df: pd.DataFrame, key: str, column_config: dict | None = None, **kwargs):
    """Tabla en la que al pulsar una fila se devuelve su índice (o None)."""
    event = st.dataframe(
        df,
        key=key,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config=column_config,
        **kwargs,
    )
    rows = event.selection.rows if event and event.selection else []
    return rows[0] if rows else None
