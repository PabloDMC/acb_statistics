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

# Si no se define en el .env, por defecto creará la carpeta 'data' en la raíz
DATA_ROOT = Path(os.getenv("DATA_BASE_DIR", PROJECT_ROOT / "data"))
DATABASE_NAME = Path(os.getenv("DATA_BASE_NAME", "acb_analytics.duckdb"))

LANDING_DIR = DATA_ROOT / "landing"
DATABASE_PATH = DATA_ROOT / "database" / DATABASE_NAME

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