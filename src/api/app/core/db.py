"""
Gestión de la conexión a DuckDB.

DuckDB no es un servidor: es un fichero. La estrategia aquí es:
- Abrir UNA conexión de solo lectura al arrancar la aplicación (lifespan).
- Por cada request, sacar un `cursor()` de esa conexión. Los cursores de
  DuckDB son ligeros y seguros para lecturas concurrentes desde varios
  threads/requests sobre la misma conexión de solo lectura.

Así evitamos abrir/cerrar el fichero en cada petición y evitamos también
compartir un único cursor mutable entre requests concurrentes.
"""

from contextlib import contextmanager
from typing import Iterator

import duckdb

from app.core.config import get_settings


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._connection: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        # read_only=True: la API nunca debe escribir en el warehouse analítico.
        self._connection = duckdb.connect(database=self._path, read_only=True)

    def disconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None:
            raise RuntimeError("La base de datos no está conectada todavía.")
        return self._connection

    @contextmanager
    def cursor(self) -> Iterator[duckdb.DuckDBPyConnection]:
        cur = self.connection.cursor()
        try:
            yield cur
        finally:
            cur.close()


# Instancia única compartida por toda la aplicación (se conecta en el lifespan de main.py)
database = Database(path=get_settings().duckdb_path)


def get_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """Dependencia de FastAPI: entrega un cursor DuckDB por request."""
    with database.cursor() as cur:
        yield cur
