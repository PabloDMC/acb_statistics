"""
Punto de entrada de la app de Streamlit.

    streamlit run src/app/streamlit_app.py

(con la API levantada; su URL se cambia con la variable de entorno ACB_API_URL)
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="ACB Statistics", page_icon=":material/sports_basketball:", layout="wide")

import backend  # noqa: E402

# En Streamlit Community Cloud la API se arranca aquí mismo (ver backend.py); en local no hace nada
backend.ensure()

import components  # noqa: E402  (después de set_page_config)
import filters  # noqa: E402
from nav import PAGES  # noqa: E402

page = st.navigation(list(PAGES.values()))

with st.sidebar:
    st.markdown("### ACB Statistics")
    components.search_box(st.sidebar, key="sidebar_search")
    st.divider()
filters.sidebar()
st.sidebar.caption(
    "Datos: [ACB](https://www.acb.com). Proyecto personal sin relación con la ACB · "
    "[código](https://github.com/PabloDMC/acb_statistics)"
)

page.run()
