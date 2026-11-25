"""
API embebida para Streamlit Community Cloud.

Community Cloud solo ejecuta la app de Streamlit, así que la API (FastAPI) se arranca aquí mismo
como un proceso hijo en 127.0.0.1:8000: no queda expuesta a internet y la app le habla igual que
en local. La base de datos se descarga del dataset privado de Hugging Face.

Se activa solo si existe ACB_DB_DATASET y NO existe ACB_API_URL (en local, o en Docker, la API se
levanta aparte y esto no hace nada). En Community Cloud, ACB_DB_DATASET y HF_TOKEN se ponen en los
"Secrets" de la app, que Streamlit expone como variables de entorno.

Actualizaciones: cada hora (como mucho) se mira si el dataset tiene una versión nueva de la base.
Si la hay, se descarga, se reinicia la API con ella y se vacía la caché de la app. Así, lo que
publica scripts/publish_db.py llega a la web sin tocar nada más.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import streamlit as st

API_PORT = 8000
API_DIR = Path(__file__).resolve().parents[1] / "api"
DATA_DIR = Path(os.getenv("ACB_DATA_DIR") or Path.home() / "acb_data")
CHECK_EVERY_S = 3600


def enabled() -> bool:
    return bool(os.getenv("ACB_DB_DATASET")) and not os.getenv("ACB_API_URL")


class _Backend:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.sha: str | None = None
        self.db_path: Path | None = None
        self.checked_at = 0.0

    @staticmethod
    def _repo() -> tuple[str, str | None, str]:
        return (os.environ["ACB_DB_DATASET"], os.getenv("HF_TOKEN"),
                os.getenv("ACB_DB_FILENAME", "acb_analytics.duckdb"))

    def _latest_sha(self) -> str:
        from huggingface_hub import HfApi

        repo, token, _ = self._repo()
        return HfApi(token=token).dataset_info(repo).sha

    def _download(self, sha: str) -> Path:
        from huggingface_hub import hf_hub_download

        repo, token, filename = self._repo()
        dest = DATA_DIR / sha[:12]
        return Path(hf_hub_download(repo_id=repo, filename=filename, repo_type="dataset",
                                    revision=sha, token=token, local_dir=dest))

    def _start(self, db_path: Path) -> subprocess.Popen:
        env = {**os.environ, "ACB_DUCKDB_PATH": str(db_path)}
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
            cwd=API_DIR, env=env,
        )
        for _ in range(120):
            if proc.poll() is not None:
                raise RuntimeError("La API no ha arrancado (mira los logs de la app).")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{API_PORT}/health", timeout=2)
                return proc
            except Exception:
                time.sleep(1)
        proc.terminate()
        raise RuntimeError("La API no responde tras 2 minutos.")

    def ensure(self) -> bool:
        """Deja la API en marcha con la última base publicada. Devuelve True si la ha (re)arrancado
        (entonces hay que vaciar la caché de la app)."""
        with self.lock:
            alive = self.proc is not None and self.proc.poll() is None
            if alive and time.time() - self.checked_at < CHECK_EVERY_S:
                return False
            self.checked_at = time.time()
            try:
                sha = self._latest_sha()
            except Exception:
                if alive:  # Hugging Face no responde: se sigue con la base que hay
                    return False
                raise
            if alive and sha == self.sha:
                return False

            new_path = self._download(sha)  # se descarga antes de parar la API: corte mínimo
            old_path = self.db_path
            if alive:
                self.proc.terminate()
                self.proc.wait(timeout=30)
            self.proc = self._start(new_path)
            self.sha, self.db_path = sha, new_path
            if old_path is not None and old_path.parent != new_path.parent:
                shutil.rmtree(old_path.parent, ignore_errors=True)
            return True


@st.cache_resource(show_spinner=False)
def _backend() -> _Backend:
    return _Backend()


def ensure() -> None:
    if not enabled():
        return
    with st.spinner("Preparando los datos… (tras un rato sin visitas, la primera carga tarda un minuto)"):
        if _backend().ensure():
            st.cache_data.clear()
