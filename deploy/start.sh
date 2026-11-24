#!/usr/bin/env bash
# Arranque del contenedor: descarga la base (si se indica un dataset de Hugging Face), levanta la
# API en local (127.0.0.1:8000, no expuesta) y Streamlit en el puerto público ($PORT).
set -euo pipefail

if [ -n "${ACB_DB_DATASET:-}" ]; then
  echo "Descargando la base desde el dataset ${ACB_DB_DATASET}..."
  python - <<'PY'
import os, shutil
from huggingface_hub import hf_hub_download
src = hf_hub_download(
    repo_id=os.environ["ACB_DB_DATASET"],
    filename=os.environ.get("ACB_DB_FILENAME", "acb_analytics.duckdb"),
    repo_type="dataset",
    token=os.environ.get("HF_TOKEN"),
)
dest = os.environ["ACB_DUCKDB_PATH"]
os.makedirs(os.path.dirname(dest), exist_ok=True)
shutil.copyfile(src, dest)
print("Base lista en", dest)
PY
fi

if [ ! -f "${ACB_DUCKDB_PATH}" ]; then
  echo "No encuentro la base en ${ACB_DUCKDB_PATH} (define ACB_DB_DATASET o monta el fichero)." >&2
  exit 1
fi

(cd src/api && uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1) &

# esperar a que la API responda antes de abrir la app
python - <<'PY'
import time, urllib.request
for _ in range(60):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        break
    except Exception:
        time.sleep(1)
PY

exec streamlit run src/app/streamlit_app.py \
  --server.port "${PORT}" --server.address 0.0.0.0 --server.headless true \
  --server.runOnSave false --server.enableXsrfProtection false --server.enableCORS false \
  --browser.gatherUsageStats false
