"""
Posesión y quintetos en pista de cada evento del play-by-play.

Sustituye a int_possessions.py e int_lineups.py. Este modelo solo hace la parte secuencial
(recorrer el partido en orden); las agregaciones viven en SQL: int_possessions e int_stints.

Cómo se cuentan las posesiones
------------------------------
No se decide "cuándo cambia la posesión" mirando el evento siguiente. Se marca qué equipo ATACA
en cada evento que lo identifica sin ambigüedad (tiro, tiro libre, rebote, pérdida) y una posesión
es una racha consecutiva de marcadores del mismo equipo dentro de un cuarto. Un 2+1, un rebote
ofensivo o una antideportiva con balón no necesitan regla propia: el mismo equipo sigue marcando.

Únicas excepciones: apuntes contables del feed de la ACB que no son cambios de posesión.
Tras una técnica, antideportiva o descalificante:
  1. el tiro libre de una técnica no identifica atacante (el balón vuelve a quien lo tenía);
  2. la "pérdida" que el feed anota al infractor después de esos tiros libres no es un cambio
     de posesión (sí cuenta como pérdida en el boxscore oficial).
Y en una tanda de tiros libres:
  3. el rebote defensivo que el feed apunta entre dos tiros libres del mismo lanzador (en el mismo
     segundo y sin otro marcador entre medias) es el rebote "de equipo" del primer fallo: el
     lanzador sigue tirando, así que no cambia la posesión (partido 18281, 4º cuarto).

Salida: una fila por evento (match_id, event_idx) con
    is_offense_marker   el evento identifica al equipo atacante
    event_kind          '', 'technical_ft', 'bookkeeping_turnover' o 'between_ft_rebound'
    offense_team_id     equipo en posesión durante el evento
    possession_seq      número de posesión dentro del partido
    stint_seq           número de tramo (mismos 10 jugadores en pista) dentro del partido
    home_lineup / away_lineup   ids de los jugadores en pista, ordenados y unidos por '-'
"""
import numpy as np
import pandas as pd

# --- tipos de jugada -------------------------------------------------------------------------
FT_MADE, FT_MISS = 92, 96
FG_MADE = {93, 94, 100}
FG_MISS = {97, 98, 533}
FT = {FT_MADE, FT_MISS}
OREB, DREB, TOV = 101, 104, 106
STARTER, SUB_IN, SUB_OUT = 599, 112, 115

TECH = {172, 176, 177, 537, 538, 539, 540, 541, 542, 544, 545}      # 1 TL, el balón no cambia
UNSPORT = {165, 166, 167, 169, 170, 171, 548, 549, 551}             # 2 TL + posesión
# 168, 173, 543, 547 son faltas "offset" (dobles) y 200 es la expulsión en sí: sin TL ni pérdida contable

LIVE = FG_MADE | FG_MISS | {OREB, DREB}
MARKERS = LIVE | FT | {TOV}

INPUT_COLUMNS = [
    "match_id", "event_idx", "quarter", "seconds_remaining", "play_type_id",
    "player_id", "team_id", "home_team_id", "away_team_id",
]
OUTPUT_COLUMNS = {
    "match_id": "int64",
    "event_idx": "int64",
    "is_offense_marker": "bool",
    "event_kind": "object",
    "offense_team_id": "Int64",
    "possession_seq": "int64",
    "stint_seq": "int64",
    "home_lineup": "object",
    "away_lineup": "object",
}


def _offense_markers(df):
    """Equipo atacante en cada evento marcador (NaN en el resto) y tipo de apunte contable."""
    pt = df.play_type_id.to_numpy()
    team = df.team_id.to_numpy()
    home = df.home_team_id.to_numpy()
    away = df.away_team_id.to_numpy()
    match = df.match_id.to_numpy()
    quarter = df.quarter.to_numpy()
    clock = df.seconds_remaining.to_numpy()

    marker = np.full(len(df), np.nan)
    kind = [""] * len(df)
    prev_period = None
    tech_ft, book_tov, ft_seen = {}, {}, {}
    for i in range(len(df)):
        period = (match[i], quarter[i])
        if period != prev_period:
            prev_period = period
            tech_ft = {}    # equipo que lanza -> TL de técnica pendientes
            book_tov = {}   # equipo infractor -> pérdidas contables pendientes
            ft_seen = {}    # equipo infractor -> ¿el rival ya lanzó algún TL desde la falta?
        p, t = pt[i], team[i]

        if p in TECH or p in UNSPORT:
            book_tov[t] = book_tov.get(t, 0) + 1
            ft_seen[t] = False
            if p in TECH:
                rival = away[i] if t == home[i] else home[i]
                tech_ft[rival] = tech_ft.get(rival, 0) + 1
            continue

        if p in FT:
            for offender in ft_seen:
                if offender != t:
                    ft_seen[offender] = True
            if tech_ft.get(t, 0) > 0:
                tech_ft[t] -= 1
                kind[i] = "technical_ft"
                continue
        elif p == TOV:
            if book_tov.get(t, 0) > 0 and ft_seen.get(t):
                book_tov[t] -= 1
                kind[i] = "bookkeeping_turnover"
                continue
        elif p == DREB and _rebound_between_fts(i, pt, team, match, quarter, clock):
            kind[i] = "between_ft_rebound"
            continue
        elif p in LIVE:     # balón vivo: lo pendiente caduca
            tech_ft.clear()
            book_tov.clear()
            ft_seen.clear()

        if p in MARKERS:
            marker[i] = t
    return marker, kind


def _rebound_between_fts(i, pt, team, match, quarter, clock):
    """El rebote defensivo i va seguido, en el mismo segundo y antes de cualquier otro marcador,
    de un tiro libre del rival (el que lanzaba): es el rebote contable de un primer TL fallado."""
    for j in range(i + 1, len(pt)):
        if match[j] != match[i] or quarter[j] != quarter[i] or clock[j] != clock[i]:
            return False
        if pt[j] in TECH or pt[j] in UNSPORT:   # los TL que vengan son de la falta, no de la tanda
            return False
        if pt[j] in MARKERS:
            return pt[j] in FT and team[j] != team[i]
    return False


def _lineups(df):
    """Quinteto local y visitante tras aplicar cada evento, como texto 'id-id-id-id-id'."""
    home_l, away_l = [], []
    on_court = {True: set(), False: set()}
    key = {True: "", False: ""}
    prev_match = None
    for match_id, pt, player, team, home in zip(
        df.match_id.to_numpy(), df.play_type_id.to_numpy(), df.player_id.to_numpy(),
        df.team_id.to_numpy(), df.home_team_id.to_numpy(),
    ):
        if match_id != prev_match:
            prev_match = match_id
            on_court = {True: set(), False: set()}
            key = {True: "", False: ""}
        if pt in (STARTER, SUB_IN, SUB_OUT) and not pd.isna(player):
            side = bool(team == home)
            if pt == SUB_OUT:
                on_court[side].discard(int(player))
            else:
                on_court[side].add(int(player))
            key[side] = "-".join(str(p) for p in sorted(on_court[side]))
        home_l.append(key[True])
        away_l.append(key[False])
    return home_l, away_l


def enrich_events(df):
    if len(df) == 0:
        return pd.DataFrame({c: pd.Series(dtype=t) for c, t in OUTPUT_COLUMNS.items()})

    ev = df[INPUT_COLUMNS].sort_values(["match_id", "event_idx"]).reset_index(drop=True)
    period = [ev.match_id, ev.quarter]

    # --- atacante y posesión ---------------------------------------------------------------
    marker, kind = _offense_markers(ev)
    ev["offense_marker"] = marker
    ev["event_kind"] = kind
    is_marker = ev.offense_marker.notna()
    ev["is_offense_marker"] = is_marker

    # equipo en posesión: último marcador visto; antes del primero del cuarto, el del primero
    grouped = ev.groupby(period).offense_marker
    ev["offense_team_id"] = grouped.ffill().fillna(grouped.bfill())

    markers_only = ev.loc[is_marker]
    prev_marker = markers_only.groupby([markers_only.match_id, markers_only.quarter]).offense_marker.shift()
    starts = pd.Series(False, index=ev.index)
    starts.loc[is_marker] = (markers_only.offense_marker != prev_marker).to_numpy()
    ev["possession_seq"] = starts.groupby(ev.match_id).cumsum()

    # los eventos previos al primer marcador del cuarto pertenecen a su primera posesión
    before_first = starts.groupby(period).cumsum() == 0
    first_seq = ev.loc[is_marker].groupby(["match_id", "quarter"]).possession_seq.first().rename("first_seq")
    ev = ev.join(first_seq, on=["match_id", "quarter"])
    ev.loc[before_first & ev.first_seq.notna(), "possession_seq"] = ev.first_seq
    ev["possession_seq"] = ev.possession_seq.astype("int64")

    # --- quintetos ---------------------------------------------------------------------------
    ev["home_lineup"], ev["away_lineup"] = _lineups(ev)
    # Un bloque de cambios = eventos de cambio consecutivos del mismo equipo en el mismo segundo;
    # dentro del bloque el quinteto es transitorio y vale el del final.
    is_sub = ev.play_type_id.isin([STARTER, SUB_IN, SUB_OUT])
    block_key = pd.DataFrame({
        "m": ev.match_id, "t": ev.team_id, "s": ev.seconds_remaining, "q": ev.quarter, "sub": is_sub,
    })
    block = (block_key != block_key.shift()).any(axis=1).cumsum()
    for col in ("home_lineup", "away_lineup"):
        last = ev.groupby(block)[col].transform("last")
        ev[col] = last.where(is_sub, ev[col])

    period = [ev.match_id, ev.quarter]
    new_stint = (
        (ev.home_lineup != ev.groupby(period).home_lineup.shift())
        | (ev.away_lineup != ev.groupby(period).away_lineup.shift())
    )
    ev["stint_seq"] = new_stint.groupby(ev.match_id).cumsum().astype("int64")

    ev["offense_team_id"] = ev.offense_team_id.astype("Int64")
    return ev[list(OUTPUT_COLUMNS)]


def model(dbt, session):

    dbt.config(
        materialized="incremental",
        schema="intermediate",
        tags=["acb_analytics"],
    )

    df = dbt.ref("int_play_by_play").project(", ".join(INPUT_COLUMNS)).df()

    if dbt.is_incremental:
        done = session.sql(f"SELECT DISTINCT match_id FROM {dbt.this}").df()
        df = df[~df.match_id.isin(done.match_id)]

    return enrich_events(df)
