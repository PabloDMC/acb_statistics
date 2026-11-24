"""
Fichas biográficas de los jugadores (fecha y lugar de nacimiento, nacionalidad, altura) desde la
web de la ACB: la página https://www.acb.com/es/liga/jugadores/{player_id} trae esos datos en el
HTML (payload de Next.js) con el mismo id de jugador que la API. La API de partidos no los tiene.

Descarga solo los jugadores que aún no están en data/landing/acbweb_player_bio/ (cada ficha es un
JSON pequeño), con pocas peticiones en paralelo y una pausa entre ellas para no cargar la web.

    python -m src.ingestion.player_bio            # jugadores nuevos
    python -m src.ingestion.player_bio --refresh  # todos de nuevo (p. ej. una vez por temporada)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from src.common.config import LANDING_DIR

LOG = logging.getLogger("ACB_PlayerBio")
URL = "https://www.acb.com/es/liga/jugadores/{player_id}"
OUT_DIR = Path(LANDING_DIR) / "acbweb_player_bio"
FIELDS = ("birthDate", "birthPlace", "birthCountry", "nationality", "height")
HEADERS = {"User-Agent": "Mozilla/5.0 (acb_statistics; proyecto personal de estadísticas)"}


def known_player_ids() -> set[int]:
    """Jugadores que aparecen en algún boxscore descargado."""
    ids: set[int] = set()
    for f in (Path(LANDING_DIR) / "apiacb_boxscore").glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for tb in data.get("teamBoxscores") or []:
            for sp in tb.get("statsByPeriods") or []:
                for p in (sp.get("stats") or {}).get("players") or []:
                    pid = (p.get("player") or {}).get("id")
                    if pid:
                        ids.add(int(pid))
    return ids


def parse_bio(html: str) -> dict:
    """Extrae los campos del bloque de la persona. El payload viene con las comillas escapadas
    (\\"birthDate\\":\\"15-12-1995\\"); se busca a partir de birthDate para no confundir
    "height" o "nationality" con otras apariciones de la página."""
    start = html.find('birthDate\\":')
    if start < 0:
        return {}
    block = html[start - 2: start + 800]
    out = {}
    for key in FIELDS:
        m = re.search(r'\\"' + key + r'\\":\\"([^"\\]*)\\"', block)
        out[key] = m.group(1) if m else None
    return out


def fetch_one(session: requests.Session, player_id: int) -> tuple[int, dict | None]:
    try:
        resp = session.get(URL.format(player_id=player_id), headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return player_id, None
        bio = parse_bio(resp.text)
        return player_id, {"player_id": player_id, **bio, "source": "acb.com"}
    except requests.RequestException as exc:
        LOG.warning(f"{player_id}: {exc}")
        return player_id, None
    finally:
        time.sleep(0.3)


def run(refresh: bool = False, workers: int = 4) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ids = known_player_ids()
    todo = sorted(ids if refresh else {i for i in ids if not (OUT_DIR / f"{i}.json").exists()})
    LOG.info(f"{len(ids)} jugadores conocidos, {len(todo)} fichas por descargar")
    ok = 0
    with requests.Session() as session, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_one, session, pid) for pid in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            pid, bio = fut.result()
            if bio is not None:
                (OUT_DIR / f"{pid}.json").write_text(json.dumps(bio, ensure_ascii=False), encoding="utf-8")
                ok += 1
            if n % 100 == 0:
                LOG.info(f"{n}/{len(todo)}")
    LOG.info(f"Fichas guardadas: {ok}/{len(todo)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    run(refresh=args.refresh)
