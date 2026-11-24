"""
Sondeo de cobertura del histórico de la API de la ACB (NO descarga temporadas enteras).

Para cada edición de cada competición pide unos pocos partidos (de una ronda del principio, otra
de mitad y otra del final) y mira qué trae cada uno: cabecera, boxscore (con minutos por jugador),
jugada a jugada y tiros con coordenadas. Con la tabla resultante se decide qué temporadas
descargar y qué tratar como incompleto.

    python scripts/probe_history.py                 # todas las ediciones que no tenemos
    python scripts/probe_history.py --editions 60 70 80
    python scripts/probe_history.py --per-round 1   # más rápido

Salida: prototypes/qa/results/history_coverage.csv (una fila por partido sondeado) y un resumen
por edición en pantalla. Hace unas 15-20 llamadas por edición.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common.config import ACB_API_KEY, ACB_BASE_URL, COMPETITIONS, LANDING_DIR  # noqa: E402
from src.ingestion.api_acb_client import ApiAcbClient  # noqa: E402

OUT = ROOT / "prototypes" / "qa" / "results" / "history_coverage.csv"


def editions_in_landing() -> set[int]:
    ids = set()
    for f in (Path(LANDING_DIR) / "apiacb_boxscore").glob("ed_*_m_*.json"):
        ids.add(int(f.name.split("_")[1]))
    return ids


def probe_match(client: ApiAcbClient, match_id: int) -> dict:
    row = {"match_id": match_id}
    header = client.get_match_header(match_id) or {}
    row["header"] = bool(header)
    row["status"] = header.get("matchStatus")
    row["start"] = header.get("start")
    content = header.get("availableContent") or {}
    row["header_says_pbp"] = content.get("playbyplay")

    box = client.get_boxscore(match_id) or {}
    players = minutes = 0
    for tb in box.get("teamBoxscores") or []:
        for sp in tb.get("statsByPeriods") or []:
            if sp.get("quarter") != 0:
                continue
            for p in (sp.get("stats") or {}).get("players") or []:
                players += 1
                pt = p.get("playTime") or ""
                minutes += 1 if pt.replace(":", "").strip("0") else 0
    row["box_players"] = players
    row["box_players_with_minutes"] = minutes
    row["box_has_periods"] = any(sp.get("quarter") not in (0, None)
                                 for tb in box.get("teamBoxscores") or [] for sp in tb.get("statsByPeriods") or [])

    pbp = client.get_play_by_play(match_id) or {}
    plays = pbp.get("plays") or []
    row["pbp_events"] = len(plays)
    row["pbp_subs"] = sum(1 for p in plays if p.get("playType") in (112, 115))

    shots = client.get_match_shots(match_id) or {}
    pts = shots.get("shotPoints") or []
    row["shots"] = len(pts)
    row["shots_with_xy"] = sum(1 for s in pts if s.get("posX") is not None and s.get("posY") is not None)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--editions", type=int, nargs="+")
    parser.add_argument("--per-round", type=int, default=2, help="Partidos por ronda sondeada")
    args = parser.parse_args()

    client = ApiAcbClient(base_url=ACB_BASE_URL, api_key=ACB_API_KEY)
    have = editions_in_landing()
    rows = []
    for comp_id in COMPETITIONS:
        payload = client.get_competition(comp_id) or {}
        for comp in payload.get("competitions", []):
            for ed in comp.get("editions", []):
                ed_id = ed.get("id")
                if args.editions and ed_id not in args.editions:
                    continue
                if not args.editions and ed_id in have:
                    continue
                rounds = ed.get("rounds") or []
                if not rounds:
                    continue
                picks = {rounds[0]["id"], rounds[len(rounds) // 2]["id"], rounds[-1]["id"]}
                n_matches = 0
                for rnd in picks:
                    ml = client.get_matchlist(rnd) or {}
                    matches = [m for m in ml.get("matches") or [] if m.get("id")]
                    for m in matches[: args.per_round]:
                        r = probe_match(client, m["id"])
                        r.update({"competition_id": comp_id, "edition_id": ed_id,
                                  "season": f"{ed.get('seasonStartYear')}-{ed.get('seasonEndYear')}",
                                  "rounds_in_edition": len(rounds), "round_id": rnd})
                        rows.append(r)
                        n_matches += 1
                        time.sleep(0.2)
                ed_rows = [r for r in rows if r["edition_id"] == ed_id and r["competition_id"] == comp_id]
                if ed_rows:
                    print(
                        f"comp {comp_id} ed {ed_id} ({ed_rows[0]['season']}): {n_matches} partidos · "
                        f"boxscore {sum(r['box_players'] > 0 for r in ed_rows)}/{n_matches} "
                        f"(minutos {sum(r['box_players_with_minutes'] > 0 for r in ed_rows)}) · "
                        f"jugada a jugada {sum(r['pbp_events'] > 0 for r in ed_rows)} "
                        f"(con cambios {sum(r['pbp_subs'] > 0 for r in ed_rows)}) · "
                        f"tiros {sum(r['shots_with_xy'] > 0 for r in ed_rows)}",
                        flush=True,
                    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\n{len(rows)} partidos sondeados -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
