import os
from pathlib import Path
from dotenv import load_dotenv

# ==============================================================================
# 1. RUTAS DEL SISTEMA (Detección dinámica de directorios)
# ==============================================================================
SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent

# Buscamos el archivo .env en la raíz del proyecto y lo cargamos en memoria
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

def _resolve(value, default: Path) -> Path:
    """Ruta del .env (relativa a la raíz del proyecto si no es absoluta) o el valor por defecto."""
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


DATA_ROOT = PROJECT_ROOT / "data"

# DATA_BASE_DIR es la carpeta de la BASE DE DATOS, no la raíz de datos. Antes se usaba como
# raíz y, con DATA_BASE_DIR="./data/database", el landing acababa en data/database/landing:
# la ingesta no encontraba nada de lo ya descargado y lo bajaba todo otra vez.
DATABASE_DIR = _resolve(os.getenv("DATA_BASE_DIR"), DATA_ROOT / "database")
DATABASE_NAME = Path(os.getenv("DATA_BASE_NAME", "acb_analytics.duckdb"))
DATABASE_PATH = DATABASE_DIR / DATABASE_NAME

# El landing es el mismo que lee dbt (var landing_data_dir = ../data/landing). Se puede mover
# con LANDING_DIR en el .env, cambiando también esa variable de dbt.
LANDING_DIR = _resolve(os.getenv("LANDING_DIR"), DATA_ROOT / "landing")

# ==============================================================================
# 2. CONFIGURACIÓN DE LA API ACB
# ==============================================================================
ACB_BASE_URL = "https://api2.acb.com/api/matchdata/"

# IDs fijos de las competiciones de interés (Liga, Copa, Supercopa)
COMPETITIONS = [1, 2, 3] 

# ==============================================================================
# 3. SEGURIDAD Y PARÁMETROS DE RENDIMIENTO
# ==============================================================================
ACB_API_KEY = os.getenv("ACB_API_KEY")
#if not ACB_API_KEY:
#    raise ValueError("CRÍTICO: La variable 'ACB_API_KEY' no está configurada en el archivo .env")

ENV = os.getenv("ENV", "dev").lower()
MAX_WORKERS = 15 if ENV == "dev" else 5