"""
Punto único de conversión "resultado SQL de DuckDB" -> "estructuras JSON-safe".

Este módulo existe para resolver, de una vez por todas, el problema descrito
en el resumen del proyecto: numpy.int64, numpy.ndarray, numpy.bool_, Decimal,
date/datetime, etc. no siempre son serializables directamente por FastAPI.

En lugar de arreglar esto endpoint a endpoint, todo repositorio pasa sus
resultados por `rows_to_dicts()` antes de devolverlos hacia arriba.
"""

from __future__ import annotations

import datetime
import decimal
from typing import Any, Iterable

import duckdb


def _coerce_value(value: Any) -> Any:
    # Import perezoso de numpy: si algún día no está disponible, el resto
    # del módulo sigue funcionando para tipos nativos de Python.
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None  # type: ignore

    if value is None:
        return None

    if np is not None:
        if isinstance(value, np.generic):
            # np.int64, np.float64, np.bool_... -> escalar nativo de Python
            return value.item()
        if isinstance(value, np.ndarray):
            return [_coerce_value(v) for v in value.tolist()]

    if isinstance(value, (list, tuple)):
        return [_coerce_value(v) for v in value]

    if isinstance(value, dict):
        return {k: _coerce_value(v) for k, v in value.items()}

    if isinstance(value, decimal.Decimal):
        return float(value)

    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()

    # DuckDB puede devolver structs/arrays anidados ya como dict/list nativos
    return value


def cursor_to_dicts(cursor: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """
    Toma un cursor DuckDB que ya ejecutó una query (cursor.execute(...)) y
    devuelve una lista de dicts JSON-safe, usando cursor.description para
    los nombres de columna.
    """
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    return [
        {col: _coerce_value(val) for col, val in zip(columns, row)}
        for row in rows
    ]


def row_to_dict(cursor: duckdb.DuckDBPyConnection) -> dict[str, Any] | None:
    """Igual que cursor_to_dicts pero para cuando esperas como mucho una fila."""
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    row = cursor.fetchone()
    if row is None:
        return None
    return {col: _coerce_value(val) for col, val in zip(columns, row)}


def scalar(cursor: duckdb.DuckDBPyConnection) -> Any:
    """Para queries tipo SELECT COUNT(*) ...: devuelve el primer valor escalar."""
    row = cursor.fetchone()
    if row is None:
        return None
    return _coerce_value(row[0])


def build_paginated_response(
    items: Iterable[dict[str, Any]], total: int, limit: int, offset: int
) -> dict[str, Any]:
    return {
        "items": list(items),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }
