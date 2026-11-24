"""Sube el código de la app al Space de Hugging Face (lo usa el flujo de GitHub en cada push a main;
también se puede lanzar a mano).

Uso:
    python scripts/deploy_space.py

Variables: HF_TOKEN (escritura), HF_READ_TOKEN (lectura, opcional), HF_SPACE ("usuario/nombre"), ACB_DB_DATASET (para configurar la
variable del Space que indica de dónde descargar la base).

El Space solo recibe lo necesario para servir: Dockerfile, requirements-serve.txt, src/api, src/app,
.streamlit y el script de arranque. Ni la ingesta, ni dbt, ni datos, ni .env.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

# origen en el repo -> destino en el Space
FILES = {
    "deploy/Dockerfile": "Dockerfile",
    "deploy/hf_space_README.md": "README.md",
    "deploy/start.sh": "deploy/start.sh",
    "requirements-serve.txt": "requirements-serve.txt",
    "src/__init__.py": "src/__init__.py",
}
DIRS = ["src/api", "src/app", ".streamlit"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".env", "secrets.toml")


def main() -> int:
    load_dotenv(ROOT / ".env")
    token, space = os.getenv("HF_TOKEN"), os.getenv("HF_SPACE")
    dataset = os.getenv("ACB_DB_DATASET")
    if not token or not space:
        print("Faltan HF_TOKEN y/o HF_SPACE", file=sys.stderr)
        return 1

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for src, dst in FILES.items():
            (out / dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / src, out / dst)
        for d in DIRS:
            shutil.copytree(ROOT / d, out / d, ignore=IGNORE)
        api.upload_folder(
            folder_path=str(out),
            repo_id=space,
            repo_type="space",
            commit_message="Deploy desde GitHub",
            delete_patterns="*",  # lo que ya no exista en el repo se borra del Space
        )

    # Configuración del Space: de dónde bajar la base y con qué token (el dataset es privado).
    # Mejor un token de SOLO LECTURA (HF_READ_TOKEN): el Space no necesita escribir nada.
    if dataset:
        api.add_space_variable(space, "ACB_DB_DATASET", dataset)
        api.add_space_secret(space, "HF_TOKEN", os.getenv("HF_READ_TOKEN") or token)
    print(f"Desplegado en https://huggingface.co/spaces/{space}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
