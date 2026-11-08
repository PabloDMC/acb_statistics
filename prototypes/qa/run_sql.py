"""
Lanza en modo solo lectura cada consulta de prototypes/qa/queries/*.sql contra el warehouse y
guarda el resultado en prototypes/qa/results/<nombre>.csv (máx. 5.000 filas por consulta).

Uso, desde la raíz del proyecto (puede estar la API levantada; dbt build no):
    .venv\\Scripts\\python prototypes\\qa\\run_sql.py            # todas
    .venv\\Scripts\\python prototypes\\qa\\run_sql.py q01 q03    # solo las que empiezan así
"""
import csv
import sys
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from common.config import DATABASE_PATH  # noqa: E402

MAX_ROWS = 5000

queries = sorted((HERE / "queries").glob("*.sql"))
if len(sys.argv) > 1:
    queries = [q for q in queries if any(q.stem.startswith(a) for a in sys.argv[1:])]

out_dir = HERE / "results"
out_dir.mkdir(exist_ok=True)
con = duckdb.connect(str(DATABASE_PATH), read_only=True)
for q in queries:
    t0 = time.time()
    try:
        cur = con.execute(q.read_text(encoding="utf-8"))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
        with open(out_dir / f"{q.stem}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"OK    {q.stem}: {len(rows)} filas ({time.time() - t0:.1f} s)")
    except Exception as exc:  # una consulta rota no para las demás
        (out_dir / f"{q.stem}.csv").write_text(f"error\n{exc}\n", encoding="utf-8")
        print(f"ERROR {q.stem}: {exc}")
con.close()
