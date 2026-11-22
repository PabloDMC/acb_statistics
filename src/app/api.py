"""
Cliente de la API para Streamlit. La app NUNCA lee DuckDB directamente: todo pasa por la API,
así la capa de consumo se puede cambiar sin tocar los datos.

- La URL base sale de ACB_API_URL (por defecto http://localhost:8000/api/v1).
- Las respuestas se cachean 10 minutos (st.cache_data): navegar entre páginas no repite llamadas.
- Un 404 devuelve None (p. ej. un jugador sin datos en esa temporada); sin conexión, la página
  muestra un aviso y se detiene.
"""

from __future__ import annotations

import os

import requests
import streamlit as st

BASE_URL = os.getenv("ACB_API_URL", "http://localhost:8000/api/v1").rstrip("/")


@st.cache_data(ttl=600, show_spinner=False)
def _fetch(path: str, params: tuple) -> object | None:
    resp = requests.get(f"{BASE_URL}{path}", params=dict(params), timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get(path: str, **params) -> object | None:
    clean = tuple(sorted((k, v) for k, v in params.items() if v is not None))
    try:
        return _fetch(path, clean)
    except requests.ConnectionError:
        st.error(f"No puedo conectar con la API en {BASE_URL}. ¿Está levantada (uvicorn)?")
        st.stop()
    except requests.HTTPError as exc:
        st.error(f"La API respondió con un error en {path}: {exc}")
        st.stop()


def get_all(path: str, page_size: int = 500, **params) -> list:
    """Recorre una respuesta paginada ({items, total, ...}) y devuelve todos los items."""
    items, offset = [], 0
    while True:
        page = get(path, limit=page_size, offset=offset, **params)
        if not page:
            break
        items.extend(page["items"])
        offset += page_size
        if not page.get("has_more"):
            break
    return items
