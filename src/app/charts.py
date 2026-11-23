"""
Gráficos propios de la app (Plotly): carta de tiro, mapas de rotaciones y evolución del marcador.

Coordenadas de los tiros (ver README de la API): milímetros con el origen en el centro del aro;
x lateral (±7500, bandas), y hacia el centro del campo (0 = altura del aro). Las medidas de la
pista son las FIBA: línea de fondo a 1,575 m del aro, triple a 6,75 m (6,60 m en las esquinas),
zona de 4,90 m de ancho, tiro libre a 5,80 m del fondo, semicírculo de no carga de 1,25 m.
"""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

COURT_LINE = "#A1A1AA"
X_RANGE = (-7700, 7700)
Y_RANGE = (-1800, 9800)

BASELINE_Y = -1575
FT_LINE_Y = 5800 + BASELINE_Y  # 4225
THREE_R, CORNER_X = 6750, 6600
CORNER_Y = math.sqrt(THREE_R**2 - CORNER_X**2)  # donde la recta de la esquina se une al arco


def _arc(cx, cy, r, a0, a1, n=80):
    t = np.linspace(math.radians(a0), math.radians(a1), n)
    return cx + r * np.cos(t), cy + r * np.sin(t)


def court_figure(height: int = 520) -> go.Figure:
    """Media pista vacía, en milímetros y con la proporción real."""
    fig = go.Figure()
    shapes = [
        # fondo y bandas
        dict(type="rect", x0=-7500, y0=BASELINE_Y, x1=7500, y1=Y_RANGE[1] - 100, line=dict(color=COURT_LINE, width=1.5)),
        # zona y tiro libre
        dict(type="rect", x0=-2450, y0=BASELINE_Y, x1=2450, y1=FT_LINE_Y, line=dict(color=COURT_LINE, width=1.5)),
        # tablero y aro
        dict(type="line", x0=-900, y0=-375, x1=900, y1=-375, line=dict(color=COURT_LINE, width=2.5)),
        dict(type="circle", x0=-225, y0=-225, x1=225, y1=225, line=dict(color="#E8590C", width=2)),
        # esquinas del triple
        dict(type="line", x0=-CORNER_X, y0=BASELINE_Y, x1=-CORNER_X, y1=CORNER_Y, line=dict(color=COURT_LINE, width=1.5)),
        dict(type="line", x0=CORNER_X, y0=BASELINE_Y, x1=CORNER_X, y1=CORNER_Y, line=dict(color=COURT_LINE, width=1.5)),
    ]
    fig.update_layout(shapes=shapes)
    # arcos: triple, círculo de tiro libre, semicírculo de no carga
    a = math.degrees(math.atan2(CORNER_Y, CORNER_X))
    for (cx, cy, r, a0, a1, dash) in (
        (0, 0, THREE_R, a, 180 - a, None),
        (0, FT_LINE_Y, 1800, 0, 180, None),
        (0, FT_LINE_Y, 1800, 180, 360, "dot"),
        (0, 0, 1250, 0, 180, None),
    ):
        xs, ys = _arc(cx, cy, r, a0, a1)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=COURT_LINE, width=1.5, dash=dash),
                                 hoverinfo="skip", showlegend=False))
    fig.update_xaxes(range=X_RANGE, visible=False, fixedrange=True)
    fig.update_yaxes(range=Y_RANGE, visible=False, fixedrange=True, scaleanchor="x", scaleratio=1)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white",
                      legend=dict(orientation="h", y=-0.02, x=0.5, xanchor="center"))
    return fig


def _shot_text(s: dict) -> str:
    q = s.get("quarter")
    sec = s.get("seconds_remaining")
    clock = f"{sec // 60:02d}:{sec % 60:02d}" if sec is not None else ""
    period = (f"{q}º cuarto" if q <= 4 else f"Prórroga {q - 4}") if q else ""
    parts = [
        f"<b>{s['player']['name'] or ''}</b> · {'anotado' if s['made'] else 'fallado'} ({s.get('value')} pts)",
        f"{s.get('zone') or ''} · {s.get('area') or ''} · {s.get('range') or ''}",
        f"{period} {clock}" + (f" · marcador {s['score']}" if s.get("score") else ""),
    ]
    if s.get("opponent") or s.get("date"):
        parts.append(f"vs {(s.get('opponent') or {}).get('name') or ''} · {s.get('date') or ''}")
    if s.get("is_clutch"):
        parts.append("Clutch")
    return "<br>".join(parts)


def shot_points(shots: list[dict], height: int = 520) -> go.Figure:
    """Cada tiro como un punto: anotados en verde, fallados como cruz roja."""
    fig = court_figure(height)
    for made, name, color, symbol in ((True, "Anotado", "#2F9E44", "circle"), (False, "Fallado", "#E03131", "x")):
        sel = [s for s in shots if bool(s["made"]) == made]
        fig.add_trace(go.Scattergl(
            x=[s["x"] for s in sel], y=[s["y"] for s in sel], mode="markers", name=f"{name} ({len(sel)})",
            marker=dict(color=color, symbol=symbol, size=7, opacity=0.7, line=dict(width=0)),
            text=[_shot_text(s) for s in sel],
            hovertemplate="%{text}<extra></extra>",
        ))
    return fig


def _hex_bin(xs: np.ndarray, ys: np.ndarray, size: float) -> tuple[np.ndarray, np.ndarray]:
    """Coordenadas axiales (q, r) del hexágono (de radio `size`, vértice arriba) de cada punto."""
    q = (math.sqrt(3) / 3 * xs - ys / 3) / size
    r = (2 / 3 * ys) / size
    # redondeo en coordenadas cúbicas
    x, z = q, r
    y = -x - z
    rx, ry, rz = np.round(x), np.round(y), np.round(z)
    dx, dy, dz = np.abs(rx - x), np.abs(ry - y), np.abs(rz - z)
    fix_x = (dx > dy) & (dx > dz)
    fix_y = ~fix_x & (dy > dz)
    rx = np.where(fix_x, -ry - rz, rx)
    ry = np.where(fix_y, -rx - rz, ry)
    rz = np.where(~fix_x & ~fix_y, -rx - ry, rz)
    return rx.astype(int), rz.astype(int)


# Escala de tu función original (src/shots.py): 5 colores, cortes en ±2, ±7 y ±15 puntos
ZONE_COLORS = ["#2b7cb6", "#abd9e9", "#f2f2f2", "#fdaf61", "#d7191c"]
ZONE_BOUNDS = [-7, -2, 2, 7]
ZONE_LABELS = ["< −7", "−7 a −2", "±2", "+2 a +7", "> +7"]


def _bucket(diff: float) -> int:
    for i, b in enumerate(ZONE_BOUNDS):
        if diff < b:
            return i
    return len(ZONE_BOUNDS)


def shot_hexes(
    shots: list[dict],
    league_pct_by_zone: dict[int, float],
    hex_size: float = 450,
    height: int = 520,
) -> go.Figure:
    """
    Carta de tiro por zonas (como la función original de src/shots.py): cada hexágono está donde
    se tiró, su tamaño (tres escalones) es el volumen de tiro de ese punto y su color, el acierto
    del jugador EN SU ZONA frente a la media de la liga en esa zona. Así el color no depende de
    los pocos tiros de un hexágono, sino de toda la zona.
    """
    fig = court_figure(height)
    shots = [s for s in shots if s["y"] <= Y_RANGE[1] - 600 and s.get("zone_id") is not None]
    if not shots:
        return fig

    # acierto del jugador por zona y diferencia con la liga
    zone_tot: dict[int, list[int]] = {}
    for s in shots:
        z = zone_tot.setdefault(s["zone_id"], [0, 0])
        z[0] += 1
        z[1] += 1 if s["made"] else 0
    zone_pct = {z: m / n for z, (n, m) in zone_tot.items()}
    zone_name = {s["zone_id"]: f"{s.get('zone') or ''} · {s.get('area') or ''}" for s in shots}

    # los triples frontales (zonas 10-12) se separan un poco de la línea, como en la función original
    xs = np.array([s["x"] * (1.12 if s["zone_id"] in (10, 11, 12) else 1) for s in shots], dtype=float)
    ys = np.array([s["y"] * (1.12 if s["zone_id"] in (10, 11, 12) else 1) for s in shots], dtype=float)
    q, r = _hex_bin(xs, ys, hex_size)
    cells: dict[tuple[int, int], list[dict]] = {}
    for qi, ri, s in zip(q, r, shots):
        cells.setdefault((qi, ri), []).append(s)

    counts = sorted(len(v) for v in cells.values())
    p33 = counts[int(0.33 * (len(counts) - 1))]
    p66 = counts[int(0.66 * (len(counts) - 1))]

    buckets: dict[int, dict[str, list]] = {i: {"x": [], "y": [], "size": [], "text": []} for i in range(5)}
    for (qi, ri), cell in cells.items():
        diffs = [100 * (zone_pct[s["zone_id"]] - league_pct_by_zone[s["zone_id"]])
                 for s in cell if league_pct_by_zone.get(s["zone_id"]) is not None]
        if not diffs:
            continue
        diff = sum(diffs) / len(diffs)
        n = len(cell)
        scale = 0.4 if n < p33 else (1.0 if n > p66 else 0.7)
        zid = max({s["zone_id"] for s in cell}, key=lambda z: sum(1 for s in cell if s["zone_id"] == z))
        b = buckets[_bucket(diff)]
        b["x"].append(hex_size * math.sqrt(3) * (qi + ri / 2))
        b["y"].append(hex_size * 1.5 * ri)
        b["size"].append(26 * scale)
        lg = league_pct_by_zone.get(zid)
        b["text"].append(
            f"{zone_name[zid]}<br>En la zona: {100 * zone_pct[zid]:.0f}% ({zone_tot[zid][1]}/{zone_tot[zid][0]})"
            + (f" · liga {100 * lg:.0f}%" if lg is not None else "")
            + f"<br>Tiros en este punto: {n}"
        )
    for i, b in buckets.items():
        fig.add_trace(go.Scatter(
            x=b["x"] or [None], y=b["y"] or [None], mode="markers", name=ZONE_LABELS[i],
            marker=dict(symbol="hexagon", size=b["size"] or [10], color=ZONE_COLORS[i],
                        line=dict(width=0.6, color="#71717A")),
            text=b["text"], hovertemplate="%{text}<extra></extra>",
        ))
    fig.update_layout(legend=dict(title="vs liga (puntos %)", orientation="h", y=-0.02, x=0.5, xanchor="center"))
    return fig


def rotation_heatmap(rotations: dict, height: int | None = None) -> go.Figure:
    """Mapa de rotaciones de la temporada: % de partidos en pista por jugador y minuto (0-39)."""
    players = rotations["players"]
    names = [p["player"]["name"] or str(p["player"]["id"]) for p in players]
    z = [[m["pct_games_on_court"] or 0 for m in p["minutes"]] for p in players]
    text = [[f"{100 * (m['pct_games_on_court'] or 0):.0f}% de los partidos · {m['avg_seconds'] or 0:.0f} s de media"
             for m in p["minutes"]] for p in players]
    fig = go.Figure(go.Heatmap(
        z=z, x=[m + 0.5 for m in range(40)], y=names, text=text, hovertemplate="%{y} · min %{x:.0f}<br>%{text}<extra></extra>",
        colorscale=[[0, "#FFF7ED"], [1, "#9A3412"]], zmin=0, zmax=1, xgap=1, ygap=2,
        colorbar=dict(title="% partidos", tickformat=".0%", thickness=12),
    ))
    _rotation_axes(fig, len(names), height)
    return fig


def match_rotation(stints: list[dict], team_id: int, bin_seconds: int = 15, height: int | None = None) -> go.Figure:
    """Rotación de un partido: una barra por jugador, oscura en los tramos en que estuvo en pista (sin prórrogas)."""
    n_bins = 2400 // bin_seconds
    on: dict[int, np.ndarray] = {}
    names: dict[int, str] = {}
    first_seen: dict[int, float] = {}
    for s in stints:
        if s["team"]["id"] != team_id or (s.get("quarter") or 0) > 4:
            continue
        start = (s["quarter"] - 1) * 600 + (600 - s["start_time"])
        end = (s["quarter"] - 1) * 600 + (600 - s["end_time"])
        if end <= start:
            continue
        for p in s["players"]:
            pid = p["id"]
            names[pid] = p["name"] or str(pid)
            arr = on.setdefault(pid, np.zeros(n_bins))
            first_seen[pid] = min(first_seen.get(pid, start), start)
            # fracción de cada intervalo que pasa en pista
            for b in range(int(start // bin_seconds), min(n_bins, int(math.ceil(end / bin_seconds)))):
                lo, hi = b * bin_seconds, (b + 1) * bin_seconds
                arr[b] += max(0.0, min(hi, end) - max(lo, start)) / bin_seconds
    # titulares primero (en pista desde el segundo 0), luego por minutos
    order = sorted(on, key=lambda pid: (first_seen[pid] > 0, -on[pid].sum()))
    z = [np.clip(on[pid], 0, 1).tolist() for pid in order]
    minutes = [on[pid].sum() * bin_seconds / 60 for pid in order]
    labels = [f"{names[pid]} ({m:.0f}')" for pid, m in zip(order, minutes)]
    xs = [(b + 0.5) * bin_seconds / 60 for b in range(n_bins)]
    fig = go.Figure(go.Heatmap(
        z=z, x=xs, y=labels, colorscale=[[0, "#F4F4F5"], [1, "#9A3412"]], zmin=0, zmax=1,
        showscale=False, ygap=3, hovertemplate="%{y}<br>min %{x:.1f}<extra></extra>",
    ))
    _rotation_axes(fig, len(labels), height)
    return fig


def _rotation_axes(fig: go.Figure, n_rows: int, height: int | None) -> None:
    for q in (10, 20, 30):
        fig.add_vline(x=q, line=dict(color="#52525B", width=1, dash="dot"))
    fig.update_xaxes(range=[0, 40], dtick=5, title="Minuto", fixedrange=True)
    fig.update_yaxes(autorange="reversed", fixedrange=True)
    fig.update_layout(height=height or max(260, 28 * n_rows + 80), margin=dict(l=10, r=10, t=10, b=10),
                      plot_bgcolor="white")


def _elapsed_minutes(quarter: int, seconds_remaining: int) -> float:
    if quarter <= 4:
        return ((quarter - 1) * 600 + (600 - seconds_remaining)) / 60
    return (2400 + (quarter - 5) * 300 + (300 - seconds_remaining)) / 60


def game_flow(events: list[dict], home: str, away: str,
              home_color: str = "rgba(232,89,12,0.55)", away_color: str = "rgba(25,113,194,0.55)") -> go.Figure:
    """Diferencia en el marcador (local - visitante) a lo largo del partido."""
    xs, margin, labels = [0.0], [0], ["0-0"]
    last = (0, 0)
    max_q = 4
    for e in events:
        h, a = e.get("score_home"), e.get("score_away")
        if h is None or a is None or (h, a) == last:
            continue
        max_q = max(max_q, e["quarter"])
        t = _elapsed_minutes(e["quarter"], e.get("seconds_remaining") or 0)
        # escalón: el marcador cambia en el instante del evento
        xs += [t, t]
        margin += [margin[-1], h - a]
        labels += [labels[-1], f"{h}-{a}"]
        last = (h, a)
    end = 40 + 5 * (max_q - 4)
    xs.append(end)
    margin.append(margin[-1])
    labels.append(labels[-1])

    m = np.array(margin, dtype=float)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=np.clip(m, 0, None), fill="tozeroy", mode="lines", line=dict(width=0),
                             fillcolor=home_color, name=f"Por delante {home}", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=np.clip(m, None, 0), fill="tozeroy", mode="lines", line=dict(width=0),
                             fillcolor=away_color, name=f"Por delante {away}", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=m, mode="lines", line=dict(color="#18181B", width=1.5), showlegend=False,
                             text=labels, hovertemplate="min %{x:.1f}<br>%{text}<extra></extra>"))
    for q in range(1, max_q):
        x = 10 * q if q <= 4 else 40 + 5 * (q - 4)
        fig.add_vline(x=x, line=dict(color="#A1A1AA", width=1, dash="dot"))
    lim = max(5, int(np.abs(m).max()) + 2)
    fig.update_yaxes(range=[-lim, lim], title=f"← {away} · {home} →", zeroline=True, zerolinecolor="#52525B")
    fig.update_xaxes(range=[0, end], dtick=5, title="Minuto")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                      legend=dict(orientation="h", y=1.08))
    return fig


def lineup_scatter(combos: list[dict]) -> go.Figure:
    """Explorador de quintetos: rating ofensivo frente a defensivo, tamaño = posesiones."""
    fig = go.Figure()
    if not combos:
        return fig
    poss = np.array([c.get("possessions") or 0 for c in combos], dtype=float)
    fig.add_trace(go.Scatter(
        x=[c.get("offensive_rating") for c in combos],
        y=[c.get("defensive_rating") for c in combos],
        mode="markers",
        marker=dict(size=8 + 30 * np.sqrt(poss / poss.max()), color=[c.get("net_rating") for c in combos],
                    colorscale="RdYlGn", cmid=0, line=dict(width=0.5, color="white"),
                    colorbar=dict(title="Net", thickness=12)),
        text=[f"{', '.join(p['name'] or '' for p in c['players'])}<br>{c.get('possessions')} posesiones · "
              f"Net {c.get('net_rating') or 0:+.1f}" for c in combos],
        hovertemplate="%{text}<br>ORtg %{x:.1f} · DRtg %{y:.1f}<extra></extra>",
        showlegend=False,
    ))
    fig.update_yaxes(autorange="reversed", title="DRtg (arriba = mejor defensa)")
    fig.update_xaxes(title="ORtg (derecha = mejor ataque)")
    fig.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white")
    return fig
