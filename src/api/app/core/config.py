"""
Configuración central de la API.

Antes esto usaba una ruta relativa por defecto ("./acb_analytics.duckdb"),
que solo funciona si arrancas uvicorn desde el directorio exacto donde
está el fichero. Eso es justo lo "hardcodeado"/fragil que había que evitar.

Ahora:
- Calculamos la raíz del repo de forma absoluta a partir de la ubicación de
  este propio fichero (src/api/app/core/config.py -> sube 4 niveles ->
  raíz del proyecto ACB_STATISTICS). Esto NO depende de tu directorio de
  trabajo al lanzar uvicorn.
- Leemos el .env de la RAÍZ del repo (el mismo que ya usa tu ingesta), no
  uno nuevo. Así solo mantienes un .env.
- Cualquier variable ACB_* en ese .env (o en el entorno real, p.ej. en
  Docker/CI) sobreescribe estos valores por defecto automáticamente:
  pydantic-settings ya hace esa lectura, no hay que tocar nada más.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> core -> app -> api -> src -> RAÍZ DEL REPO
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACB_",
        env_file=str(_REPO_ROOT / ".env"),
        extra="ignore",
    )

    # Por defecto apunta a data/database/ dentro del repo, pero cualquier
    # ACB_DUCKDB_PATH en el .env (o variable de entorno real) gana siempre.
    duckdb_path: str = str(_REPO_ROOT / "data" / "database" / "acb_analytics.duckdb")

    api_prefix: str = "/api/v1"
    default_page_size: int = 50
    max_page_size: int = 500

    project_name: str = "ACB Statistics API"
    version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    """Cacheado: se lee una sola vez por proceso."""
    return Settings()
