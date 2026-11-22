from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import api
import components
import filters
import nav
import tables

sel = filters.current()
if not sel:
    st.stop()

st.title(f"Temporada {sel['edition_name']}")
st.caption(sel["competition_name"] + (f" · {sel['competition_phase']}" if sel["competition_phase"] else " · todas las fases"))

# Clasificación y evolución: siempre de la liga regular si la fase elegida no tiene clasificación
std_phase = sel["competition_phase"] or ("LR" if "LR" in sel["phases"] else None)

tab_std, tab_evo, tab_lead, tab_players, tab_teams = st.tabs(
    ["Clasificación", "Evolución", "Líderes", "Jugadores", "Equipos"]
)

# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------
with tab_std:
    standings = api.get(
        "/standings", edition_id=sel["edition_id"], competition_id=sel["competition_id"], competition_phase=std_phase
    ) if std_phase else None
    if not standings:
        st.info("No hay clasificación para esta competición y fase.")
    else:
        df = pd.DataFrame([
            {
                "Pos": r["position"],
                "Logo": r["logo"],
                "Equipo": r["team"]["name"],
                "PJ": r["games"],
                "V": r["wins"],
                "D": r["losses"],
                "%V": components.pct(r["win_pct"]),
                "PF": r["points_for"],
                "PC": r["points_against"],
                "Dif": r["point_diff"],
                "Local": f"{r['home_wins']}-{r['home_losses']}",
                "Visitante": f"{r['away_wins']}-{r['away_losses']}",
                "Racha": r["streak"],
                "Últimos 5": r["last5"],
                "_id": r["team"]["id"],
            }
            for r in standings["rows"]
        ])
        row = components.selectable_table(
            df.drop(columns="_id"),
            key="season_standings",
            column_config={
                "Logo": st.column_config.ImageColumn("", width="small"),
                "%V": st.column_config.NumberColumn("%V", format="%.1f"),
            },
            height=35 * len(df) + 38,
        )
        st.caption(f"Pulsa un equipo para ver su página. Desempate: {standings['tiebreak']}")
        if row is not None:
            nav.goto("equipo", id=int(df.iloc[row]["_id"]))

# ---------------------------------------------------------------------------
# Evolución de la clasificación
# ---------------------------------------------------------------------------
with tab_evo:
    hist = api.get(
        "/standings/history", edition_id=sel["edition_id"], competition_id=sel["competition_id"], competition_phase=std_phase
    ) if std_phase else None
    if not hist or not hist["rounds"]:
        st.info("No hay jornadas para dibujar la evolución.")
    else:
        teams = {t["team"]["id"]: t for t in hist["teams"]}
        names = {tid: t["team"]["name"] for tid, t in teams.items()}
        default = [t["team"]["id"] for t in hist["teams"][:4]]
        chosen = st.multiselect(
            "Equipos destacados",
            options=list(names),
            default=default,
            format_func=lambda tid: names[tid],
            key="evo_teams",
        )
        series: dict[int, list[tuple[int, int]]] = {}
        for rnd in hist["rounds"]:
            for p in rnd["positions"]:
                series.setdefault(p["team_id"], []).append((rnd["round"], p["position"]))

        palette = ["#E8590C", "#1971C2", "#2F9E44", "#AE3EC9", "#F08C00", "#0C8599", "#C2255C", "#5C940D"]
        fig = go.Figure()
        # primero los no destacados, en gris, para que queden debajo
        for tid, pts in series.items():
            if tid in chosen:
                continue
            fig.add_trace(go.Scatter(
                x=[r for r, _ in pts], y=[p for _, p in pts], mode="lines",
                line={"color": "#D4D4D8", "width": 1.5}, name=names.get(tid), hoverinfo="name+y", showlegend=False,
            ))
        for i, tid in enumerate(chosen):
            pts = series.get(tid, [])
            color = palette[i % len(palette)]
            fig.add_trace(go.Scatter(
                x=[r for r, _ in pts], y=[p for _, p in pts], mode="lines+markers",
                line={"color": color, "width": 3}, marker={"size": 5}, name=names.get(tid),
                hovertemplate="%{fullData.name}<br>Jornada %{x}: %{y}º<extra></extra>",
            ))
        n_teams = len(teams)
        fig.update_yaxes(autorange=False, range=[n_teams + 0.5, 0.5], dtick=1, title="Posición")
        fig.update_xaxes(dtick=1 if len(hist["rounds"]) <= 20 else 2, title="Jornada")
        fig.update_layout(height=560, margin={"l": 10, "r": 10, "t": 10, "b": 10}, legend={"orientation": "h", "y": -0.12},
                          plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Líderes
# ---------------------------------------------------------------------------
LEADER_METRICS = [
    ("points", "Puntos"), ("rebounds", "Rebotes"), ("assists", "Asistencias"),
    ("steals", "Robos"), ("blocks", "Tapones"), ("rating", "Valoración"),
]
PER_LABELS = {"per_game": "Por partido", "total": "Totales", "per_40_min": "Por 40 min", "per_100_poss": "Por 100 posesiones"}

with tab_lead:
    c1, c2 = st.columns([3, 1])
    per = c1.segmented_control(
        "Escala", options=list(PER_LABELS), format_func=PER_LABELS.get, default="per_game", key="lead_per"
    ) or "per_game"
    min_games = c2.number_input("Mínimo de partidos", min_value=0, max_value=60, value=5, step=1, key="lead_min")
    cols = st.columns(3)
    for i, (metric, label) in enumerate(LEADER_METRICS):
        with cols[i % 3]:
            st.markdown(f"**{label}**")
            lb = api.get(
                "/leaderboards/players", metric=metric, per=per, min_games=min_games, limit=10,
                **filters.api_filters(sel),
            ) or []
            if not lb:
                st.caption("Sin datos.")
                continue
            df = pd.DataFrame([
                {
                    "#": e["rank"],
                    label: e["value"],
                    "Jugador": e["player"]["name"],
                    "Equipo": e["club_team"]["team"]["name"],
                    "_id": e["player"]["id"],
                }
                for e in lb
            ])
            row = components.selectable_table(
                df.drop(columns="_id"),
                key=f"lead_{metric}",
                column_config={label: st.column_config.NumberColumn(label, format="%d" if per == "total" else "%.1f")},
            )
            if row is not None:
                nav.goto("jugador", id=int(df.iloc[row]["_id"]))

# ---------------------------------------------------------------------------
# Tabla de jugadores
# ---------------------------------------------------------------------------
P_PER = {"per_game": "Por partido", "total": "Totales", "per_36": "Por 36 min", "per_100": "Por 100 posesiones"}

with tab_players:
    c1, c2, c3 = st.columns([2, 2, 1])
    p_per = c1.segmented_control("Escala", options=list(P_PER), format_func=P_PER.get, default="per_game", key="pl_per") or "per_game"
    group = c2.segmented_control("Columnas", options=list(tables.PLAYER_GROUPS), default="Básicas", key="pl_group") or "Básicas"
    p_min = c3.number_input("Mín. partidos", min_value=0, max_value=60, value=5, step=1, key="pl_min")

    items = api.get_all("/stats/players", per=p_per, min_games=p_min, sort="-points", **filters.api_filters(sel))
    if not items:
        st.info("Sin datos para esta selección.")
    else:
        base = {
            "Jugador": lambda it: it["player"]["name"],
            "Equipo": lambda it: it["club_team"]["team"]["name"],
            "Fase": lambda it: it["context"]["competition_phase"],
            "PJ": lambda it: it["games"],
            "Min": lambda it: it.get("minutes"),
        }
        df, config = tables.build(items, tables.PLAYER_GROUPS[group], base, integer_counts=p_per == "total")
        df["_id"] = [it["player"]["id"] for it in items]
        config["Min"] = st.column_config.NumberColumn("Min", format="%.1f")
        if sel["competition_phase"]:
            df = df.drop(columns="Fase")
        row = components.selectable_table(df.drop(columns="_id"), key="season_players", column_config=config, height=600)
        st.caption(f"{len(df)} jugadores. Pulsa una fila para ver su página; pulsa una cabecera para ordenar.")
        if row is not None:
            nav.goto("jugador", id=int(df.iloc[row]["_id"]))

# ---------------------------------------------------------------------------
# Tabla de equipos
# ---------------------------------------------------------------------------
T_PER = {"per_game": "Por partido", "total": "Totales", "per_100": "Por 100 posesiones"}

with tab_teams:
    c1, c2 = st.columns([2, 3])
    t_per = c1.segmented_control("Escala", options=list(T_PER), format_func=T_PER.get, default="per_game", key="tm_per") or "per_game"
    t_group = c2.segmented_control("Columnas", options=list(tables.TEAM_GROUPS), default="Básicas", key="tm_group") or "Básicas"

    items = api.get_all("/stats/teams", per=t_per, **filters.api_filters(sel))
    if not items:
        st.info("Sin datos para esta selección.")
    else:
        base = {
            "Logo": lambda it: it.get("logo"),
            "Equipo": lambda it: it["club_team"]["team"]["name"],
            "Fase": lambda it: it["context"]["competition_phase"],
            "PJ": lambda it: it["games"],
            "V": lambda it: it.get("wins"),
            "D": lambda it: it.get("losses"),
        }
        df, config = tables.build(items, tables.TEAM_GROUPS[t_group], base, integer_counts=t_per == "total")
        df["_id"] = [it["club_team"]["team"]["id"] for it in items]
        config["Logo"] = st.column_config.ImageColumn("", width="small")
        if sel["competition_phase"]:
            df = df.drop(columns="Fase")
        row = components.selectable_table(df.drop(columns="_id"), key="season_teams", column_config=config,
                                          height=35 * len(df) + 38)
        if t_per == "per_100":
            st.caption("Por 100 posesiones al ritmo medio de los partidos con jugada a jugada.")
        if row is not None:
            nav.goto("equipo", id=int(df.iloc[row]["_id"]))
