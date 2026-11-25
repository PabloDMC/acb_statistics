"""
Filtros de la app. La lógica es siempre la misma:

- Barra lateral = contexto de temporada (temporada, competición y fase). Solo aparece en las
  páginas que tratan de una temporada entera: Inicio, Temporada y Líderes y récords.
- Páginas de una entidad (Jugador, Equipo) = filtros propios arriba, debajo del nombre, que se
  aplican a todas sus secciones. Por defecto: Liga regular (sin mezclar Copa, Supercopa ni
  playoffs). La página Partido no tiene filtros.
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

    # Streamlit borra el estado de un widget en cuanto una página no lo pinta (al pasar por Jugador o
    # Equipo, que no tienen barra lateral): se restaura desde la última selección guardada
    last = st.session_state.get("season") or {}
    if "f_edition" not in st.session_state and last.get("edition_id") in by_id:
        st.session_state["f_edition"] = last["edition_id"]
        st.session_state["f_competition"] = last.get("competition_id")
        st.session_state["f_phase"] = last.get("competition_phase") or ALL_PHASES

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


def coverage(edition_id: int | None, competition_id: int | None) -> dict:
    """Qué datos hay en una temporada y competición. Antes de 2016-17 la ACB solo da el boxscore
    final: ni jugada a jugada (quintetos, rotaciones, posesiones, clutch) ni tiros."""
    for e in _editions():
        if e["id"] == edition_id:
            for c in e["competitions"]:
                if c["id"] == competition_id:
                    return c.get("coverage") or {}
    return {}


def has_play_by_play(edition_id: int | None, competition_id: int | None) -> bool:
    # sin información (API antigua) se asume que sí, para no esconder nada por error
    return coverage(edition_id, competition_id).get("has_play_by_play", True)


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


# ---------------------------------------------------------------------------
# Filtros de las páginas de jugador y equipo
# ---------------------------------------------------------------------------
PHASE_NAMES = {"LR": "Liga regular", "PO": "Playoffs", "CR": "Copa del Rey", "SC": "Supercopa"}
ALL = 0  # "toda la carrera" / "todas las competiciones"


def phase_name(code: str | None) -> str:
    return "Todas" if code in (None, ALL_PHASES) else PHASE_NAMES.get(code, code)


def _keep_valid(key: str, options: list, default) -> None:
    """Si el valor guardado de un selector ya no es una opción (cambió otro filtro), vuelve al defecto."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = default


def entity_filters(contexts: list[dict], key: str, with_edition: bool = True) -> dict:
    """
    Temporada, competición y fase de una página de jugador o equipo, en una fila. `contexts` son las
    combinaciones que existen (dicts con edition_id, edition_name, competition_id, competition_name
    y phase). Por defecto: toda la carrera, Liga Endesa y Liga regular, si existen.
    Devuelve los filtros para la API (edition_id, competition_id, competition_phase; None = todos).
    """
    cols = st.columns(3 if with_edition else 2)
    edition_id = None
    if with_edition:
        eds = sorted({(c["edition_id"], c["edition_name"]) for c in contexts}, reverse=True)
        ed_names = {ALL: "Toda la carrera", **dict(eds)}
        ed_opts = [ALL] + [e for e, _ in eds]
        _keep_valid(f"{key}_ed", ed_opts, ALL)
        edition_id = cols[0].selectbox("Temporada", ed_opts, format_func=ed_names.get, key=f"{key}_ed") or None
    in_ed = [c for c in contexts if edition_id is None or c["edition_id"] == edition_id]

    comps = sorted({(c["competition_id"], c["competition_name"]) for c in in_ed})
    comp_names = {ALL: "Todas", **dict(comps)}
    comp_opts = [ALL] + [c for c, _ in comps]
    _keep_valid(f"{key}_comp", comp_opts, 1 if 1 in comp_opts else ALL)
    competition_id = cols[-2].selectbox("Competición", comp_opts, format_func=comp_names.get, key=f"{key}_comp") or None
    in_comp = [c for c in in_ed if competition_id is None or c["competition_id"] == competition_id]

    order = list(PHASE_NAMES)
    phases = sorted({c["phase"] for c in in_comp if c.get("phase")},
                    key=lambda p: order.index(p) if p in order else len(order))
    phase_opts = [ALL_PHASES] + phases
    _keep_valid(f"{key}_phase", phase_opts, "LR" if "LR" in phases else ALL_PHASES)
    phase = cols[-1].selectbox("Fase", phase_opts, format_func=phase_name, key=f"{key}_phase")
    return {
        "edition_id": edition_id,
        "competition_id": competition_id,
        "competition_phase": None if phase == ALL_PHASES else phase,
    }
