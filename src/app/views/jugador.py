from __future__ import annotations

import pandas as pd
import streamlit as st

import api
import charts
import components
import nav
import tables

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

# filas de temporada (todas): base de la pestaña Temporadas y del selector de temporada
season_rows_total = api.get_all("/stats/players", player_id=player_id, per="total", sort="-edition_id")
editions = sorted({(r["context"]["edition"]["id"], r["context"]["edition"]["name"]) for r in season_rows_total}, reverse=True)
if not editions:
    st.info("Este jugador no tiene estadísticas.")
    st.stop()

CAREER = 0
ed_names = {CAREER: "Toda la carrera", **dict(editions)}
edition_id = st.selectbox(
    "Temporada",
    options=[e for e, _ in editions] + [CAREER],
    format_func=ed_names.get,
    key=f"pl_edition_{player_id}",
)
ed_filter = None if edition_id == CAREER else edition_id

section = components.sections(['Temporadas', 'Partido a partido', 'Splits', 'Tiro', 'Impacto y quintetos', 'Máximos'], key="pl_section")

# ---------------------------------------------------------------------------
# Temporadas (como la tabla principal de Basketball Reference)
# ---------------------------------------------------------------------------
P_PER = {"per_game": "Por partido", "total": "Totales", "per_36": "Por 36 min", "per_100": "Por 100 posesiones"}
if section == "Temporadas":
    c1, c2 = st.columns([2, 2])
    per = c1.segmented_control("Escala", options=list(P_PER), format_func=P_PER.get, default="per_game", key="pl_s_per") or "per_game"
    group = c2.segmented_control("Columnas", options=list(tables.PLAYER_GROUPS), default="Básicas", key="pl_s_group") or "Básicas"
    rows = season_rows_total if per == "total" else api.get_all("/stats/players", player_id=player_id, per=per)
    rows = sorted(rows, key=lambda r: (r["context"]["edition"]["id"], r["context"]["competition"]["id"],
                                       r["context"]["competition_phase"] or ""), reverse=True)
    base = {
        "Temporada": lambda it: it["context"]["edition"]["name"],
        "Competición": lambda it: it["context"]["competition"]["name"],
        "Fase": lambda it: it["context"]["competition_phase"],
        "Equipo": lambda it: it["club_team"]["team"]["name"],
        "PJ": lambda it: it["games"],
        "Tit": lambda it: it.get("games_started"),
        "Min": lambda it: it.get("minutes"),
    }
    df, config = tables.build(rows, tables.PLAYER_GROUPS[group], base, integer_counts=per == "total")
    config["Min"] = st.column_config.NumberColumn("Min", format="%d" if per == "total" else "%.1f")
    st.dataframe(df, hide_index=True, use_container_width=True, column_config=config)

# ---------------------------------------------------------------------------
# Partido a partido
# ---------------------------------------------------------------------------
if section == "Partido a partido":
    games = api.get_all(f"/players/{player_id}/games", edition_id=ed_filter, sort="-match_id")
    if not games:
        st.info("Sin partidos.")
    else:
        df = pd.DataFrame([
            {
                "Competición": g["context"]["competition"]["name"],
                "Fase": g["context"]["competition_phase"],
                "Rival": ("vs " if g.get("is_home") else "@ ") + ((g.get("opponent") or {}).get("name") or ""),
                "Min": round((g.get("seconds") or 0) / 60, 1),
                "Pts": g.get("points"),
                "Reb": g.get("rebounds"),
                "Ast": g.get("assists"),
                "Rob": g.get("steals"),
                "Tap": g.get("blocks"),
                "Pér": g.get("turnovers"),
                "TC": f"{g['field_goals']['made']}/{g['field_goals']['attempted']}",
                "T3": f"{g['three_pointers']['made']}/{g['three_pointers']['attempted']}",
                "TL": f"{g['free_throws']['made']}/{g['free_throws']['attempted']}",
                "+/-": g.get("plus_minus"),
                "Val": g.get("rating"),
                "_id": g["match_id"],
            }
            for g in games
        ])
        row = components.selectable_table(df.drop(columns="_id"), key=f"pl_games_{player_id}", height=520)
        st.caption(f"{len(df)} partidos jugados. Pulsa uno para ver el boxscore.")
        if row is not None:
            nav.goto("partido", id=int(df.iloc[row]["_id"]))

# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------
SPLIT_NAMES = {"location": "Local / visitante", "result": "Resultado", "role": "Titular / suplente",
               "month": "Mes", "opponent": "Rival", "clutch": "Clutch"}
if section == "Splits":
    splits = api.get(f"/players/{player_id}/splits", edition_id=ed_filter) or []
    if not splits:
        st.info("Sin datos.")
    else:
        def per_game(s, key):
            v = s["stats"].get(key)
            return None if v is None or not s["games"] else v / s["games"]

        rows = [
            {
                "Split": SPLIT_NAMES.get(s["split"], s["split"]),
                "Valor": s.get("label") or s["key"],
                "PJ": s["games"],
                "Min": None if s.get("seconds") is None else s["seconds"] / 60 / s["games"],
                "Pts": per_game(s, "points"),
                "Reb": per_game(s, "total_rebounds"),
                "Ast": per_game(s, "assists"),
                "Pér": per_game(s, "turnovers"),
                "TC%": components.pct(s["stats"].get("field_goals_pct")),
                "T3%": components.pct(s["stats"].get("three_pointers_pct")),
                "TL%": components.pct(s["stats"].get("free_throws_pct")),
                "+/-": per_game(s, "plus_minus"),
                "Val": per_game(s, "rating"),
            }
            for s in splits
        ]
        df = pd.DataFrame(rows)
        fmt = {c: st.column_config.NumberColumn(c, format="%.1f") for c in df.columns if c not in ("Split", "Valor", "PJ")}
        for name in SPLIT_NAMES.values():
            part = df[df["Split"] == name]
            if part.empty:
                continue
            st.markdown(f"**{name}**")
            st.dataframe(part.drop(columns="Split"), hide_index=True, use_container_width=True, column_config=fmt)
        st.caption("Medias por partido. Clutch: últimos 5 minutos del último cuarto y prórrogas con ±5 puntos "
                   "(solo partidos con jugada a jugada; sin minutos).")

# ---------------------------------------------------------------------------
# Tiro: perfil y zonas frente a la media de la liga
# ---------------------------------------------------------------------------
if section == "Tiro":
    shooting = api.get(f"/players/{player_id}/shooting", edition_id=ed_filter) or []
    if not shooting:
        st.info("Sin datos de tiro.")
    else:
        labels = [
            f"{s['context']['edition']['name']} · {s['context']['competition']['name']} {s['context']['competition_phase'] or ''} · {s['club_team']['team']['name']}"
            for s in shooting
        ]
        idx = st.selectbox("Contexto", options=range(len(shooting)), format_func=lambda i: labels[i], key=f"pl_shoot_{player_id}")
        s = shooting[idx]
        cols = st.columns(5)
        for col, (key, name) in zip(cols, [("field_goals", "TC"), ("two_pointers", "T2"), ("three_pointers", "T3"),
                                           ("free_throws", "TL"), ("dunks", "Mates")]):
            sp = s.get(key) or {}
            col.metric(f"{name} · {sp.get('made') or 0}/{sp.get('attempted') or 0}",
                       "–" if not sp.get("attempted") else f"{components.pct(sp.get('pct')):.0f}%")
        league = {z["zone_id"]: z for z in (api.get("/league/shot-zones", edition_id=s["context"]["edition"]["id"]) or [])}
        zrows = []
        for z in s.get("zones") or []:
            lg = league.get(z.get("zone_id"), {})
            zrows.append({
                "Zona": z["zone"],
                "Lado": z.get("area"),
                "Distancia": z.get("range"),
                "Intentos": z.get("attempted"),
                "Aciertos": z.get("made"),
                "%": components.pct(z.get("pct")),
                "% liga": components.pct(lg.get("pct")),
                "Dif. vs liga": None if z.get("pct") is None or lg.get("pct") is None else 100 * (z["pct"] - lg["pct"]),
                "Frecuencia %": components.pct(z.get("frequency")),
            })
        if zrows:
            st.markdown("**Por zona, frente a la media de la liga**")
            st.dataframe(
                pd.DataFrame(zrows), hide_index=True, use_container_width=True,
                column_config={c: st.column_config.NumberColumn(c, format="%.1f")
                               for c in ("%", "% liga", "Dif. vs liga", "Frecuencia %")},
            )
        c1, c2 = st.columns([3, 1])
        mode = c1.segmented_control("Carta de tiro", options=["Hexágonos", "Puntos"], default="Hexágonos",
                                    key=f"pl_shot_mode_{player_id}") or "Hexágonos"
        clutch = c2.toggle("Solo clutch", key=f"pl_shot_clutch_{player_id}")
        shots = api.get(
            f"/players/{player_id}/shots",
            edition_id=s["context"]["edition"]["id"], competition_id=s["context"]["competition"]["id"],
            competition_phase=s["context"]["competition_phase"], team_id=s["club_team"]["team"]["id"],
            clutch_only=clutch,
        ) or []
        if shots:
            league_pct = {zid: z.get("pct") for zid, z in league.items()}
            fig = charts.shot_hexes(shots, league_pct) if mode == "Hexágonos" else charts.shot_points(shots)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Hexágonos: tamaño = volumen de tiro; color = acierto frente a la media de la liga en esa zona "
                       "(rojo, mejor; azul, peor).")
        else:
            st.caption("Sin tiros con coordenadas en este contexto.")

# ---------------------------------------------------------------------------
# Impacto y quintetos
# ---------------------------------------------------------------------------
if section == "Impacto y quintetos":
    impact = api.get(f"/players/{player_id}/impact", edition_id=ed_filter) or []
    if impact:
        df = pd.DataFrame([
            {
                "Temporada": i["context"]["edition"]["name"],
                "Competición": i["context"]["competition"]["name"],
                "Fase": i["context"]["competition_phase"],
                "Posesiones en pista": i.get("possessions_on_court"),
                "ORtg en pista": i.get("on_court_offensive_rating"),
                "DRtg en pista": i.get("on_court_defensive_rating"),
                "Net en pista": i.get("on_court_net_rating"),
                "Net en banquillo": i.get("off_court_net_rating"),
                "On/Off": i.get("on_off_net_rating"),
                "+/- por 100": i.get("on_court_plus_minus_per_100"),
            }
            for i in impact
        ])
        st.markdown("**Rendimiento del equipo con él en pista y en el banquillo** (por 100 posesiones)")
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(c, format="%.1f") for c in df.columns[4:]})
    lineups = api.get(f"/players/{player_id}/lineups", edition_id=ed_filter, limit=15) or []
    if lineups:
        df = pd.DataFrame([
            {
                "Compañeros": ", ".join(t["name"] or str(t["id"]) for t in l.get("teammates") or []),
                "Min": l.get("minutes"),
                "Posesiones": l.get("possessions"),
                "ORtg": l.get("offensive_rating"),
                "DRtg": l.get("defensive_rating"),
                "Net": l.get("net_rating"),
                "+/-": l.get("plus_minus"),
            }
            for l in lineups
        ])
        st.markdown("**Quintetos en los que más ha jugado**")
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(c, format="%.1f") for c in ("Min", "ORtg", "DRtg", "Net")})
    if not impact and not lineups:
        st.info("Sin datos de quintetos (solo partidos con jugada a jugada).")

# ---------------------------------------------------------------------------
# Máximos en un partido
# ---------------------------------------------------------------------------
HIGH_NAMES = {"points": "Puntos", "rebounds": "Rebotes", "assists": "Asistencias", "steals": "Robos",
              "blocks": "Tapones", "three_pointers_made": "Triples", "field_goals_made": "Tiros de campo",
              "free_throws_made": "Tiros libres", "plus_minus": "+/-", "rating": "Valoración",
              "seconds_played": "Minutos"}
if section == "Máximos":
    highs = api.get(f"/players/{player_id}/game-highs", edition_id=ed_filter)
    if not highs:
        st.info("Sin partidos.")
    else:
        df = pd.DataFrame([
            {
                "Estadística": HIGH_NAMES.get(k, k),
                "Máximo": (v["value"] / 60 if k == "seconds_played" and v.get("value") is not None else v.get("value")),
                "_id": v.get("match_id"),
            }
            for k, v in highs.items()
        ])
        row = components.selectable_table(
            df.drop(columns="_id"), key=f"pl_highs_{player_id}",
            column_config={"Máximo": st.column_config.NumberColumn("Máximo", format="%.0f")},
        )
        st.caption("Pulsa una fila para abrir el partido.")
        if row is not None and pd.notna(df.iloc[row]["_id"]):
            nav.goto("partido", id=int(df.iloc[row]["_id"]))
