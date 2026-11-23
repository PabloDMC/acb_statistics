"""
Selector global de temporada, competición y fase (barra lateral). Se pinta en el punto de
entrada, así que vale para todas las páginas; las páginas leen la elección con `current()`.
"""

from __future__ import annotations

import streamlit as st

import api

ALL_PHASES = "__all__"


def _editions() -> list[dict]:
    return api.get("/editions") or []


def sidebar() -> dict:
    editions = _editions()
    if not editions:
        st.sidebar.warning("La API no devuelve temporadas.")
        return {}

    by_id = {e["id"]: e for e in editions}

    # valor inicial desde la URL (?temporada=90) la primera vez
    if "f_edition" not in st.session_state:
        qp = st.query_params.get("temporada")
        st.session_state["f_edition"] = int(qp) if qp and qp.isdigit() and int(qp) in by_id else editions[0]["id"]

    edition_id = st.sidebar.selectbox(
        "Temporada",
        options=list(by_id),
        format_func=lambda i: by_id[i]["name"] or str(i),
        key="f_edition",
    )
    comps = {c["id"]: c for c in by_id[edition_id]["competitions"]}
    if st.session_state.get("f_competition") not in comps:
        st.session_state["f_competition"] = 1 if 1 in comps else next(iter(comps))
    competition_id = st.sidebar.selectbox(
        "Competición",
        options=list(comps),
        format_func=lambda i: comps[i]["name"] or str(i),
        key="f_competition",
    )
    phases = {p["code"]: p for p in comps[competition_id]["phases"]}
    phase_options = [ALL_PHASES, *phases]
    if st.session_state.get("f_phase") not in phase_options:
        st.session_state["f_phase"] = "LR" if "LR" in phases else ALL_PHASES
    phase = st.sidebar.selectbox(
        "Fase",
        options=phase_options,
        format_func=lambda c: "Todas" if c == ALL_PHASES else (phases[c]["name"] or c),
        key="f_phase",
    )

    selection = {
        "edition_id": edition_id,
        "edition_name": by_id[edition_id]["name"],
        "competition_id": competition_id,
        "competition_name": comps[competition_id]["name"],
        "competition_phase": None if phase == ALL_PHASES else phase,
        "phases": list(phases),
    }
    st.session_state["season"] = selection
    return selection


def current() -> dict:
    """La temporada elegida en la barra lateral."""
    return st.session_state.get("season", {})


def api_filters(sel: dict | None = None, with_phase: bool = True) -> dict:
    """Filtros comunes de la API a partir de la selección."""
    sel = sel or current()
    out = {"edition_id": sel.get("edition_id"), "competition_id": sel.get("competition_id")}
    if with_phase:
        out["competition_phase"] = sel.get("competition_phase")
    return out
