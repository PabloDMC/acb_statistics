from __future__ import annotations

import pandas as pd
import streamlit as st

import api
import components
import nav

match_id = nav.read("partido", "id")
if match_id is None:
    st.title("Partido")
    st.write("Abre un partido desde el calendario de un equipo o la página de un jugador.")
    st.stop()

box = api.get(f"/matches/{match_id}/boxscore")
if not box:
    st.error(f"No existe el partido {match_id}.")
    st.stop()

m = box["match"]
ctx = m["context"]
st.caption(
    f"{ctx['competition']['name']} {ctx['edition']['name']}"
    + (f" · Jornada {m['round']}" if m.get("round") else "")
    + (f" · {m['date'][:10]}" if m.get("date") else "")
)
home_col, score_col, away_col = st.columns([3, 2, 3])
for col, side in ((home_col, "home"), (away_col, "away")):
    with col:
        if m.get(f"{side}_team_logo"):
            st.image(m[f"{side}_team_logo"], width=72)
        team = m[f"{side}_team"]
        if st.button(team["name"], key=f"goto_{side}", icon=":material/groups:"):
            nav.goto("equipo", id=team["id"])
with score_col:
    st.markdown(
        f"<div style='text-align:center;white-space:nowrap;font-size:2.6rem;font-weight:700;"
        f"padding-top:1.2rem'>{m['home_score']} – {m['away_score']}</div>",
        unsafe_allow_html=True,
    )

extra = [
    m.get("venue"),
    f"{m['attendance']:,} espectadores".replace(",", ".") if m.get("attendance") else None,
    ("Árbitros: " + ", ".join(m["referees"])) if m.get("referees") else None,
]
st.caption(" · ".join(e for e in extra if e))

# parciales por cuarto
def _qname(q: int) -> str:
    return f"{q}º" if q <= 4 else f"P{q - 4}"


if box["quarters"]:
    qdf = pd.DataFrame([
        {"Equipo": m["home_team"]["name"], **{_qname(q["quarter"]): q["home"] for q in box["quarters"]}, "Total": m["home_score"]},
        {"Equipo": m["away_team"]["name"], **{_qname(q["quarter"]): q["away"] for q in box["quarters"]}, "Total": m["away_score"]},
    ])
    st.dataframe(qdf, hide_index=True)

tab_box, tab_pbp, tab_lineups = st.tabs(["Boxscore", "Jugada a jugada", "Quintetos"])

# ---------------------------------------------------------------------------
# Boxscore
# ---------------------------------------------------------------------------
def _team_table(team: dict) -> pd.DataFrame:
    rows = []
    for p in team["players"]:
        s = p["stats"]
        played = p["played"]
        rows.append({
            "#": p.get("shirt_number"),
            "Jugador": ("* " if p.get("is_starter") else "") + (p["player"]["name"] or ""),
            "Min": p.get("minutes") if played else "No jugó",
            "Pts": s["points"] if played else None,
            "TC": f"{s['field_goals_made']}/{s['field_goals_attempted']}" if played else "",
            "T2": f"{s['two_pointers_made']}/{s['two_pointers_attempted']}" if played else "",
            "T3": f"{s['three_pointers_made']}/{s['three_pointers_attempted']}" if played else "",
            "TL": f"{s['free_throws_made']}/{s['free_throws_attempted']}" if played else "",
            "RO": s["off_rebounds"] if played else None,
            "RD": s["def_rebounds"] if played else None,
            "Reb": s["total_rebounds"] if played else None,
            "Ast": s["assists"] if played else None,
            "Rob": s["steals"] if played else None,
            "Pér": s["turnovers"] if played else None,
            "Tap": s["blocks"] if played else None,
            "FP": s["personal_fouls"] if played else None,
            "+/-": s["plus_minus"] if played else None,
            "Val": s["rating"] if played else None,
            "_id": p["player"]["id"],
        })
    t = team["totals"]
    rows.append({
        "#": "", "Jugador": "Total equipo", "Min": "",
        "Pts": t.get("points"),
        "TC": f"{t.get('field_goals_made')}/{t.get('field_goals_attempted')}",
        "T2": f"{t.get('two_pointers_made')}/{t.get('two_pointers_attempted')}",
        "T3": f"{t.get('three_pointers_made')}/{t.get('three_pointers_attempted')}",
        "TL": f"{t.get('free_throws_made')}/{t.get('free_throws_attempted')}",
        "RO": t.get("off_rebounds"), "RD": t.get("def_rebounds"), "Reb": t.get("total_rebounds"),
        "Ast": t.get("assists"), "Rob": t.get("steals"), "Pér": t.get("turnovers"), "Tap": t.get("blocks"),
        "FP": t.get("personal_fouls"), "+/-": None, "Val": t.get("rating"), "_id": None,
    })
    return pd.DataFrame(rows)


with tab_box:
    for side in ("home", "away"):
        team = box[side]
        st.markdown(f"**{team['team']['name']}**" + (f" · Entrenador: {team['coach']}" if team.get("coach") else ""))
        df = _team_table(team)
        row = components.selectable_table(df.drop(columns="_id"), key=f"box_{side}_{match_id}", height=35 * len(df) + 38)
        if row is not None and pd.notna(df.iloc[row]["_id"]):
            nav.goto("jugador", id=int(df.iloc[row]["_id"]))
    st.caption("* titular. Los totales de equipo incluyen rebotes y pérdidas de equipo. Pulsa un jugador para ver su página.")

# ---------------------------------------------------------------------------
# Jugada a jugada
# ---------------------------------------------------------------------------
with tab_pbp:
    quarters = [q["quarter"] for q in box["quarters"]] or [1, 2, 3, 4]
    qsel = st.segmented_control(
        "Cuarto", options=[0, *quarters], default=0, key=f"pbp_q_{match_id}",
        format_func=lambda q: "Todo" if q == 0 else (f"{q}º" if q <= 4 else f"Prórroga {q - 4}"),
    )
    events = api.get(f"/matches/{match_id}/play-by-play", quarter=None if not qsel else qsel) or []
    if not events:
        st.info("Este partido no tiene jugada a jugada.")
    else:
        df = pd.DataFrame([
            {
                "Cuarto": e["quarter"],
                "Reloj": e.get("clock"),
                "Equipo": (e.get("team") or {}).get("name"),
                "Jugador": (e.get("player") or {}).get("name"),
                "Jugada": e.get("play"),
                "Marcador": f"{e.get('score_home')}-{e.get('score_away')}",
                "Clutch": "●" if e.get("is_clutch") else "",
            }
            for e in events
        ])
        st.dataframe(df, hide_index=True, use_container_width=True, height=600)

# ---------------------------------------------------------------------------
# Quintetos del partido
# ---------------------------------------------------------------------------
with tab_lineups:
    stints = api.get(f"/matches/{match_id}/lineups") or []
    if not stints:
        st.info("Este partido no tiene quintetos (falta la jugada a jugada).")
    else:
        agg: dict[tuple, dict] = {}
        for s in stints:
            key = (s["team"]["id"], tuple(sorted(p["id"] for p in s["players"])))
            a = agg.setdefault(key, {"team": s["team"]["name"], "players": ", ".join(sorted(p["name"] or "" for p in s["players"])),
                                     "sec": 0, "pts": 0, "opp": 0, "pos": 0})
            a["sec"] += (s.get("start_time") or 0) - (s.get("end_time") or 0)
            a["pts"] += s.get("team_points") or 0
            a["opp"] += s.get("opponent_points") or 0
            a["pos"] += s.get("offensive_possessions") or 0
        df = pd.DataFrame([
            {"Equipo": a["team"], "Quinteto": a["players"], "Min": a["sec"] / 60,
             "Pts": a["pts"], "Pts rival": a["opp"], "+/-": a["pts"] - a["opp"], "Posesiones": a["pos"]}
            for a in agg.values()
        ]).sort_values(["Equipo", "Min"], ascending=[True, False])
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={"Min": st.column_config.NumberColumn("Min", format="%.1f")})
        st.caption("Evolución del marcador, rotaciones y carta de tiro del partido: paso 4.")
