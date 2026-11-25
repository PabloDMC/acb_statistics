from __future__ import annotations

import pandas as pd
import streamlit as st

import api
import charts
import filters
import components
import leaders
import nav
import tables

team_id = nav.read("equipo", "id")
if team_id is None:
    st.title("Equipo")
    st.write("Busca un equipo o elige uno en la clasificación:")
    components.search_box(key="team_page_search")
    st.stop()

season_rows = (api.get("/stats/teams", team_id=team_id, per="per_game") or {}).get("items", [])
if not season_rows:
    st.error(f"No hay datos del equipo {team_id}.")
    st.stop()

first = season_rows[0]
club = first["club_team"]["club"]
edition = first["context"]["edition"]
record = ", ".join(
    f"{filters.phase_name(r['context']['competition_phase'])}: {r['wins']}-{r['losses']}" for r in season_rows
)
components.entity_header(
    first["club_team"]["team"]["name"],
    f"{first['context']['competition']['name']} {edition['name']} · {record}",
    first.get("logo"),
)

# Filtros de la página: temporada y competición (cada combinación es un team_id distinto: cambiarlas
# lleva a ese equipo) y fase (se aplica a todas las secciones; por defecto, Liga regular)
cur_ed, cur_comp = edition["id"], first["context"]["competition"]["id"]
history = (api.get(f"/clubs/{club['id']}/teams") if club.get("id") else None) or []
team_of = {(h["edition"]["id"], h["competition"]["id"]): h["team"]["id"] for h in history}
team_of[(cur_ed, cur_comp)] = team_id
ed_names = {h["edition"]["id"]: h["edition"]["name"] for h in history}
ed_names.setdefault(cur_ed, edition["name"])
comp_names = {h["competition"]["id"]: h["competition"]["name"] for h in history}
comp_names.setdefault(cur_comp, first["context"]["competition"]["name"])

c1, c2, c3 = st.columns(3)
ed_opts = sorted({e for e, _ in team_of}, reverse=True)
filters._keep_valid(f"tm_ed_{team_id}", ed_opts, cur_ed)
sel_ed = c1.selectbox("Temporada", ed_opts, format_func=ed_names.get, key=f"tm_ed_{team_id}")
comp_opts = sorted(c for e, c in team_of if e == sel_ed)
filters._keep_valid(f"tm_comp_{team_id}", comp_opts, cur_comp if cur_comp in comp_opts else (1 if 1 in comp_opts else comp_opts[0]))
sel_comp = c2.selectbox("Competición", comp_opts, format_func=comp_names.get, key=f"tm_comp_{team_id}")
if (sel_ed, sel_comp) != (cur_ed, cur_comp):
    nav.goto("equipo", id=team_of[(sel_ed, sel_comp)])

phases = [r["context"]["competition_phase"] for r in season_rows]
phase_opts = [filters.ALL_PHASES] + phases
filters._keep_valid(f"tm_phase_{team_id}", phase_opts, "LR" if "LR" in phases else filters.ALL_PHASES)
sel_phase = c3.selectbox("Fase", phase_opts, format_func=filters.phase_name, key=f"tm_phase_{team_id}")
phase = None if sel_phase == filters.ALL_PHASES else sel_phase
phase_rows = [r for r in season_rows if phase is None or r["context"]["competition_phase"] == phase]

_team_pbp = filters.has_play_by_play(edition["id"], first["context"]["competition"]["id"])
section = components.sections(
    ['Plantilla', 'Calendario', 'Estadísticas', 'Tiro', 'Rotaciones', 'Quintetos', 'Líderes'] if _team_pbp
    else ['Plantilla', 'Calendario', 'Estadísticas', 'Líderes'],
    key="tm_section",
)
if not _team_pbp:
    st.caption(components.PBP_ONLY_NOTE)

# ---------------------------------------------------------------------------
# Plantilla con estadísticas
# ---------------------------------------------------------------------------
P_PER = {"per_game": "Por partido", "total": "Totales", "per_36": "Por 36 min", "per_100": "Por 100 posesiones"}
if section == "Plantilla":
    c1, c2 = st.columns(2)
    per = c1.segmented_control("Escala", options=list(P_PER), format_func=P_PER.get, default="per_game", key="tm_r_per") or "per_game"
    group = c2.segmented_control("Columnas", options=list(tables.PLAYER_GROUPS), default="Básicas", key="tm_r_group") or "Básicas"
    roster = api.get_all("/stats/players", team_id=team_id, per=per, sort="-minutes", competition_phase=phase)
    if not roster:
        st.info("Sin jugadores.")
    else:
        base = {
            "Jugador": lambda it: it["player"]["name"],
            "Pos.": lambda it: it.get("position"),
            "Fase": lambda it: it["context"]["competition_phase"],
            "PJ": lambda it: it["games"],
            "Tit": lambda it: it.get("games_started"),
            "Min": lambda it: it.get("minutes"),
        }
        df, config = tables.build(roster, tables.PLAYER_GROUPS[group], base, integer_counts=per == "total")
        df["_id"] = [it["player"]["id"] for it in roster]
        config["Min"] = st.column_config.NumberColumn("Min", format="%d" if per == "total" else "%.1f")
        if phase is not None or len(season_rows) == 1:
            df = df.drop(columns="Fase")
        row = components.selectable_table(df.drop(columns="_id"), key=f"tm_roster_{team_id}", column_config=config,
                                          height=min(35 * len(df) + 38, 700))
        if row is not None:
            nav.goto("jugador", id=int(df.iloc[row]["_id"]))

# ---------------------------------------------------------------------------
# Calendario y resultados
# ---------------------------------------------------------------------------
if section == "Calendario":
    matches = api.get_all("/matches", team_id=team_id, sort="date", competition_phase=phase)
    if not matches:
        st.info("Sin partidos.")
    else:
        rows = []
        for m in matches:
            home = m["home_team"]["id"] == team_id
            own, opp = (m["home_score"], m["away_score"]) if home else (m["away_score"], m["home_score"])
            played = m["is_played"] if m.get("is_played") is not None else (own is not None and opp is not None and (own + opp) > 0)
            rows.append({
                "Fecha": components.local_dt(m.get("date")),
                "Fase": m["context"]["competition_phase"],
                "J": m.get("round"),
                "": "vs" if home else "@",
                "Rival": m["away_team"]["name"] if home else m["home_team"]["name"],
                "Res": ("V" if own > opp else "D") if played else "",
                "Marcador": f"{own}-{opp}" if played else "Pendiente",
                "_id": m["id"],
            })
        df = pd.DataFrame(rows)
        row = components.selectable_table(df.drop(columns="_id"), key=f"tm_games_{team_id}", height=min(35 * len(df) + 38, 700))
        st.caption("Pulsa un partido para ver el boxscore.")
        if row is not None:
            nav.goto("partido", id=int(df.iloc[row]["_id"]))

# ---------------------------------------------------------------------------
# Estadísticas del equipo y del rival
# ---------------------------------------------------------------------------
if section == "Estadísticas":
    for r in phase_rows:
        st.markdown(f"**{r['context']['competition']['name']} · {r['context']['competition_phase']}** "
                    f"({r['games']} partidos, {r['wins']}-{r['losses']})")
        s = r["stats"]
        c = st.columns(4)
        c[0].metric("ORtg", f"{s.get('offensive_rating') or 0:.1f}")
        c[1].metric("DRtg", f"{s.get('defensive_rating') or 0:.1f}")
        c[2].metric("Net", f"{s.get('net_rating') or 0:+.1f}")
        c[3].metric("Ritmo", f"{s.get('possessions_per_game') or 0:.1f}")
        ff = pd.DataFrame([
            {"": "Equipo",
             "eFG%": components.pct(s.get("four_factors_efg_pct")), "TOV%": components.pct(s.get("four_factors_tov_pct")),
             "ORB%": components.pct(s.get("four_factors_orb_pct")), "TL/TCI": components.pct(s.get("four_factors_ft_rate"))},
            {"": "Rival",
             "eFG%": components.pct(s.get("opp_four_factors_efg_pct")), "TOV%": components.pct(s.get("opp_four_factors_tov_pct")),
             "ORB%": components.pct(s.get("opp_four_factors_orb_pct")), "TL/TCI": components.pct(s.get("opp_four_factors_ft_rate"))},
        ])
        st.dataframe(ff, hide_index=True, use_container_width=True,
                     column_config={k: st.column_config.NumberColumn(k, format="%.1f") for k in ("eFG%", "TOV%", "ORB%", "TL/TCI")})
        box = pd.DataFrame([
            {"": "Equipo", "Pts": s.get("points"), "TC%": components.pct(s.get("field_goals_pct")),
             "T3": s.get("three_pointers_made"), "T3%": components.pct(s.get("three_pointers_pct")),
             "TL%": components.pct(s.get("free_throws_pct")), "Reb": s.get("total_rebounds"),
             "Ast": s.get("assists"), "Rob": s.get("steals"), "Tap": s.get("blocks"), "Pér": s.get("turnovers")},
            {"": "Rival", "Pts": s.get("opponent_points"),
             "TC%": None if not s.get("opp_field_goals_attempted") else 100 * s["opp_field_goals_made"] / s["opp_field_goals_attempted"],
             "T3": s.get("opp_three_pointers_made"),
             "T3%": None if not s.get("opp_three_pointers_attempted") else 100 * s["opp_three_pointers_made"] / s["opp_three_pointers_attempted"],
             "TL%": None if not s.get("opp_free_throws_attempted") else 100 * s["opp_free_throws_made"] / s["opp_free_throws_attempted"],
             "Reb": s.get("opp_total_rebounds"), "Ast": s.get("opp_assists"), "Rob": s.get("opp_steals"),
             "Tap": s.get("opp_blocks"), "Pér": s.get("opp_turnovers")},
        ])
        st.dataframe(box, hide_index=True, use_container_width=True,
                     column_config={k: st.column_config.NumberColumn(k, format="%.1f") for k in box.columns if k})
        st.caption("Por partido.")

# ---------------------------------------------------------------------------
# Quintetos y combinaciones
# ---------------------------------------------------------------------------
SIZES = {5: "Quintetos", 4: "Cuartetos", 3: "Tríos", 2: "Parejas"}
if section == "Quintetos":
    c1, c2 = st.columns([3, 1])
    size = c1.segmented_control("Combinación", options=list(SIZES), format_func=SIZES.get, default=5, key="tm_l_size") or 5
    min_poss = c2.number_input("Mín. posesiones", min_value=0, value=50, step=10, key="tm_l_min")
    combos = api.get_all(f"/teams/{team_id}/lineups", combination_size=size, sort="-minutes", competition_phase=phase)
    combos = [c for c in combos if (c.get("possessions") or 0) >= min_poss]
    if not combos:
        st.info("Sin combinaciones con ese mínimo de posesiones.")
    else:
        st.plotly_chart(charts.lineup_scatter(combos), use_container_width=True)
        df = pd.DataFrame([
            {
                "Jugadores": ", ".join(p["name"] or str(p["id"]) for p in c["players"]),
                "Min": c.get("minutes"),
                "Posesiones": c.get("possessions"),
                "ORtg": c.get("offensive_rating"),
                "DRtg": c.get("defensive_rating"),
                "Net": c.get("net_rating"),
                "+/-": c.get("plus_minus"),
            }
            for c in combos
        ])
        st.dataframe(df, hide_index=True, use_container_width=True, height=min(35 * len(df) + 38, 700),
                     column_config={k: st.column_config.NumberColumn(k, format="%.1f") for k in ("Min", "ORtg", "DRtg", "Net")})
        st.caption("Ratings por 100 posesiones. Solo partidos con jugada a jugada.")


# ---------------------------------------------------------------------------
# Carta de tiro del equipo y de sus rivales
# ---------------------------------------------------------------------------
if section == "Tiro":
    c1, c2, c3 = st.columns([2, 2, 1])
    side = c1.segmented_control("Tiros", options=["own", "opponent"], default="own", key=f"tm_shot_side_{team_id}",
                                format_func=lambda s: "Del equipo" if s == "own" else "De los rivales") or "own"
    mode = c2.segmented_control("Vista", options=["Hexágonos", "Puntos"], default="Hexágonos", key=f"tm_shot_mode_{team_id}") or "Hexágonos"
    clutch = c3.toggle("Solo clutch", key=f"tm_shot_clutch_{team_id}")
    shots = api.get(f"/teams/{team_id}/shots", side=side, clutch_only=clutch, competition_phase=phase) or []
    if not shots:
        st.info("Sin tiros registrados.")
    else:
        league = {z["zone_id"]: z["pct"] for z in (api.get("/league/shot-zones", edition_id=edition["id"]) or [])}
        fig = charts.shot_hexes(shots, league) if mode == "Hexágonos" else charts.shot_points(shots)
        st.plotly_chart(fig, use_container_width=True)
        made = sum(1 for s in shots if s["made"])
        st.caption(f"{len(shots)} tiros de campo, {made} anotados ({100 * made / len(shots):.1f}%). " + "Hexágonos: tamaño = volumen de tiro en ese punto; color = acierto en esa zona frente a la media de la liga "
                   "en la temporada (todas las competiciones). Con «solo clutch» se comparan los tiros en clutch con esa "
                   "misma media general.")

# ---------------------------------------------------------------------------
# Mapa de rotaciones de la temporada
# ---------------------------------------------------------------------------
if section == "Rotaciones":
    rot = api.get(f"/teams/{team_id}/rotations", competition_phase=phase)
    if not rot:
        st.info("Sin datos de rotaciones (hace falta la jugada a jugada).")
    else:
        st.plotly_chart(charts.rotation_heatmap(rot), use_container_width=True)
        st.caption(f"Porcentaje de los {rot['team_games']} partidos en los que cada jugador estuvo en pista en cada "
                   "minuto (sin prórrogas). Las líneas marcan el final de cada cuarto.")


# ---------------------------------------------------------------------------
# Líderes y récords del equipo (o de toda la historia del club)
# ---------------------------------------------------------------------------
if section == "Líderes":
    scope = st.segmented_control(
        "Ámbito", options=["team", "club"], default="team", key=f"tm_lead_scope_{team_id}",
        format_func=lambda s: f"Esta temporada ({edition['name']})" if s == "team" else f"Historia del club ({club.get('name')})",
    ) or "team"
    if scope == "team" or not club.get("id"):
        leaders.render({"team_id": team_id, "competition_phase": phase}, key=f"tm_lead_{team_id}", historic=False)
    else:
        leaders.render({"club_id": club["id"], "competition_id": first["context"]["competition"]["id"], "competition_phase": phase},
                       key=f"club_lead_{club['id']}", historic=True)
