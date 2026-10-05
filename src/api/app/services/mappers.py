"""
Los repositorios devuelven filas planas (así es como sale de SQL). Los
schemas de la API son anidados a propósito (CompetitionContext, ClubTeamRef,
ShootingSplit...) porque es un contrato pensado para el consumidor, no para
el warehouse. Estas funciones hacen ese "aplanado -> anidado" en un único
sitio, para no repetir la misma transformación en cada servicio.
"""

from __future__ import annotations

from typing import Any


def competition_context(row: dict[str, Any]) -> dict:
    return {
        "competition": {"id": row.get("competition_id"), "name": row.get("competition_name")},
        "edition": {"id": row.get("edition_id"), "name": row.get("edition_name")},
        "competition_phase": row.get("competition_phase"),
    }


def club_team_ref(row: dict[str, Any]) -> dict:
    return {
        "club": {"id": row.get("club_id"), "name": row.get("club_name")},
        "team": {"id": row.get("team_id"), "name": row.get("team_name")},
    }


def shooting_split(row: dict[str, Any], prefix: str) -> dict:
    return {
        "made": row.get(f"{prefix}_made"),
        "attempted": row.get(f"{prefix}_attempted"),
        "pct": row.get(f"{prefix}_pct"),
    }


def named_ref(row: dict[str, Any], id_field: str, name_field: str) -> dict | None:
    if row.get(id_field) is None:
        return None
    return {"id": row[id_field], "name": row.get(name_field)}
