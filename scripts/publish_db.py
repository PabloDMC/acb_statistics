"""Publica la base DuckDB en el dataset de Hugging Face. La web (Streamlit Community Cloud) mira
cada hora si hay una versión nueva y la carga sola (src/app/backend.py).

Uso:
    python scripts/publish_db.py            # sube solo si hay partidos nuevos desde la última vez
    python scripts/publish_db.py --force    # sube siempre

Variables (en .env o en el entorno):
    HF_TOKEN        token de Hugging Face con permiso de escritura
    ACB_DB_DATASET  dataset donde se guarda la base, p. ej. "PabloDMC/acb-statistics-db"
    HF_SPACE        solo si la app se sirve desde un Space de Hugging Face: se reinicia tras subir
                    (opcional; con Streamlit Community Cloud no hace falta)

Por qué así:
- La base (~0,5 GB) no va en git: se guarda como fichero en un dataset de Hugging Face, que admite
  ficheros grandes gratis, y el contenedor del Space la descarga al arrancar.
- Cada subida es un commit nuevo; para no acumular medio giga por actualización, se aplasta el
  historial del dataset (super_squash_history) y solo queda la última versión.
- Se compara una "huella" (partidos jugados, último partido, jugadores) con la de la última subida
  para no reiniciar la web si no ha cambiado nada.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import duckdb
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "database" / "acb_analytics.duckdb"
STAMP_PATH = ROOT / "data" / "database" / "published.json"
DB_FILENAME = "acb_analytics.duckdb"


def fingerprint(db_path: Path) -> dict:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        played, last_start = con.execute(
            "SELECT count(*), max(match_start_time)::VARCHAR FROM main_marts.dim_matches WHERE is_played"
        ).fetchone()
        scheduled = con.execute("SELECT count(*) FROM main_marts.dim_matches").fetchone()[0]
        players = con.execute("SELECT count(*) FROM main_marts.dim_players").fetchone()[0]
    finally:
        con.close()
    return {"played": played, "last_start": last_start, "matches": scheduled, "players": players}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sube la base a Hugging Face y reinicia el Space")
    parser.add_argument("--force", action="store_true", help="Subir aunque no haya cambios")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    token = os.getenv("HF_TOKEN")
    dataset = os.getenv("ACB_DB_DATASET")
    space = os.getenv("HF_SPACE")
    if not token or not dataset:
        print("Faltan HF_TOKEN y/o ACB_DB_DATASET en .env", file=sys.stderr)
        return 1
    if not DB_PATH.exists():
        print(f"No existe {DB_PATH}", file=sys.stderr)
        return 1

    current = fingerprint(DB_PATH)
    previous = json.loads(STAMP_PATH.read_text()) if STAMP_PATH.exists() else None
    if previous == current and not args.force:
        print(f"Sin cambios desde la última publicación ({current}); no se sube nada.")
        return 0

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(dataset, repo_type="dataset", private=True, exist_ok=True)
    size_mb = DB_PATH.stat().st_size / 1e6
    print(f"Subiendo {DB_PATH.name} ({size_mb:.0f} MB) a {dataset}...")
    api.upload_file(
        path_or_fileobj=str(DB_PATH),
        path_in_repo=DB_FILENAME,
        repo_id=dataset,
        repo_type="dataset",
        commit_message=f"Base: {current['played']} partidos jugados, último {current['last_start']}",
    )
    try:
        api.super_squash_history(repo_id=dataset, repo_type="dataset")
    except Exception as exc:  # no es crítico: solo ahorra espacio
        print(f"Aviso: no se pudo aplastar el historial del dataset ({exc})")

    # la base ya está subida: se apunta antes de reiniciar, para que un fallo al reiniciar no
    # obligue a volver a subir 600 MB
    STAMP_PATH.write_text(json.dumps(current, indent=2))
    if space:
        print(f"Reiniciando el Space {space}...")
        try:
            api.restart_space(space)
        except Exception as exc:  # p. ej. el Space aún no existe (se crea con deploy_space.py)
            print(f"Aviso: no se pudo reiniciar el Space ({type(exc).__name__}). Si aún no existe, "
                  "créalo con: python scripts/deploy_space.py")
    print("Publicado:", current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
