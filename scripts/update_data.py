"""
Actualiza los datos de punta a punta: ingesta de la API de la ACB -> fichas de jugadores nuevos
(web de la ACB) -> dbt build -> resumen.

Uso, desde la raíz del proyecto y con el entorno virtual activado (la API debe estar PARADA,
porque dbt necesita escribir en la base de datos):

    python scripts/update_data.py                  # temporada en curso (lo normal tras cada jornada)
    python scripts/update_data.py --editions 90 91 # temporadas concretas
    python scripts/update_data.py --skip-ingest    # solo dbt (p. ej. tras cambiar modelos)
    python scripts/update_data.py --full-refresh   # dbt con --full-refresh (cambios en int_pbp_enriched)

Termina con código 0 si todo fue bien (los avisos de los tests no cuentan como error) y 1 si
falló la ingesta o algún modelo/test de dbt.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = ROOT / "dbt_acb"
sys.path.insert(0, str(ROOT))


def _title(text: str) -> None:
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}", flush=True)


def run_ingest(editions: list[int] | None) -> bool:
    _title("1/2  Ingesta" + (f" de las ediciones {editions}" if editions else " de la temporada en curso"))
    from src.ingestion.ingest import run_pipeline

    try:
        if editions:
            run_pipeline(is_incremental=False, target_editions=editions)
        else:
            run_pipeline(is_incremental=True)
    except Exception as exc:  # la ingesta registra sus propios errores; aquí solo paramos
        print(f"ERROR en la ingesta: {exc}")
        return False
    return True


def run_player_bio() -> None:
    """Fichas biográficas de los jugadores nuevos (web de la ACB). Un fallo aquí no para la
    actualización: las fichas son un complemento."""
    _title("Fichas de jugadores nuevos (web de la ACB)")
    from src.ingestion.player_bio import run as bio_run

    try:
        bio_run()
    except Exception as exc:
        print(f"AVISO: no se pudieron descargar las fichas: {exc}")


def _dbt_executable() -> str:
    # el dbt del mismo entorno virtual que ejecuta este script
    scripts_dir = Path(sys.executable).parent
    for name in ("dbt.exe", "dbt"):
        candidate = scripts_dir / name
        if candidate.exists():
            return str(candidate)
    found = shutil.which("dbt")
    if not found:
        raise SystemExit("No encuentro dbt: activa el entorno virtual del proyecto.")
    return found


def run_dbt(full_refresh: bool, select: str | None, threads: int) -> bool:
    _title("2/2  dbt build" + (" --full-refresh" if full_refresh else ""))
    # Pocos hilos de dbt: cada modelo de staging lee GB de JSON y DuckDB ya usa todos los núcleos
    # dentro de cada consulta; varios a la vez apenas ganan tiempo y multiplican la memoria.
    cmd = [_dbt_executable(), "build", "--threads", str(threads)]
    if full_refresh:
        cmd.append("--full-refresh")
    if select:
        cmd += ["--select", select]

    proc = subprocess.Popen(cmd, cwd=DBT_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    lock_error = False
    for line in proc.stdout:  # se muestra en directo
        print(line, end="")
        if "Could not set lock" in line or "being used by another process" in line:
            lock_error = True
    proc.wait()

    if lock_error:
        print("\nLa base de datos está bloqueada: para la API (o cualquier otra conexión) y vuelve a lanzarlo.")
    return proc.returncode == 0


def summarize() -> None:
    results_path = DBT_DIR / "target" / "run_results.json"
    if not results_path.exists():
        return
    results = json.loads(results_path.read_text(encoding="utf-8")).get("results", [])
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    _title("Resumen")
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    for r in results:
        if r["status"] in ("warn", "error", "fail"):
            name = r["unique_id"].split(".")[-1]
            print(f"  [{r['status'].upper()}] {name}: {r.get('message') or ''}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta + dbt build")
    parser.add_argument("--editions", type=int, nargs="+", help="Ediciones a descargar (por defecto, la temporada en curso)")
    parser.add_argument("--skip-ingest", action="store_true", help="No descargar nada, solo dbt")
    parser.add_argument("--full-refresh", action="store_true", help="dbt build --full-refresh")
    parser.add_argument("--select", help="Selector de dbt (por defecto, todo el proyecto)")
    parser.add_argument("--threads", type=int, default=2, help="Hilos de dbt (por defecto 2; 1 si falta memoria)")
    args = parser.parse_args()

    start = time.time()
    ok = True
    if not args.skip_ingest:
        ok = run_ingest(args.editions)
        if ok:
            run_player_bio()
    if ok:
        ok = run_dbt(args.full_refresh, args.select, args.threads)
        summarize()
    print(f"\n{'OK' if ok else 'FALLÓ'} en {time.time() - start:.0f} s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
