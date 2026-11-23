"""
Páginas de la app y navegación entre ellas.

Cada entidad tiene su página con dirección propia (?id=...), para poder compartir el enlace a un
jugador, un equipo o un partido. Para saltar desde una tabla o un botón se usa `goto()`, que deja
el id en la sesión y cambia de página; la página destino lo lee con `read()` y lo escribe en la URL.
"""

from __future__ import annotations

import streamlit as st

PAGES = {
    "inicio": st.Page("views/inicio.py", title="Inicio", icon=":material/home:", default=True),
    "temporada": st.Page("views/temporada.py", title="Temporada", icon=":material/leaderboard:", url_path="temporada"),
    "lideres": st.Page("views/lideres.py", title="Líderes y récords", icon=":material/emoji_events:", url_path="lideres"),
    "jugador": st.Page("views/jugador.py", title="Jugador", icon=":material/person:", url_path="jugador"),
    "equipo": st.Page("views/equipo.py", title="Equipo", icon=":material/groups:", url_path="equipo"),
    "partido": st.Page("views/partido.py", title="Partido", icon=":material/sports_basketball:", url_path="partido"),
}

_PENDING = "_nav_pending"


def goto(page: str, **params) -> None:
    """Ir a otra página con parámetros (p. ej. goto("jugador", id=20201774))."""
    st.session_state[_PENDING] = {"page": page, "params": params}
    st.session_state["_clear_search"] = True  # el buscador se vacía al llegar a la página
    st.switch_page(PAGES[page])


def read(page: str, name: str, cast=int):
    """Parámetro de la página: el que dejó goto() o, si no, el de la URL. Lo deja en la URL."""
    pending = st.session_state.get(_PENDING)
    if pending and pending["page"] == page and name in pending["params"]:
        value = pending["params"][name]
        pending["params"].pop(name)
        if value is not None:
            st.query_params[name] = str(value)
        return value
    raw = st.query_params.get(name)
    if raw in (None, ""):
        return None
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return None
