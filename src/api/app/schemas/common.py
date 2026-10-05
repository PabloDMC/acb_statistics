"""
Schemas compartidos por todos los recursos.

Idea clave del proyecto (punto 27 del resumen): puertas hacia fuera con
nombres, puertas hacia dentro con ids. `NamedRef` es ese patrón: se usa
para representar competición, edición/temporada, equipo y club como
"id + nombre" en cualquier respuesta, en lugar de exponer el id pelado.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class NamedRef(BaseModel):
    # Ambos opcionales: id porque un leaderboard "career" agrega varias
    # ediciones y no hay una sola id que mostrar; name porque hoy no existe
    # nombre de club en el warehouse (ver README).
    id: int | None = None
    name: str | None = None


class CompetitionContext(BaseModel):
    """Contexto de competición/temporada que acompaña a casi cualquier stat."""

    competition: NamedRef
    edition: NamedRef  # edición = temporada concreta de esa competición
    competition_phase: str | None = None


class ClubTeamRef(BaseModel):
    """
    Distinción club vs team explicada en el punto 9 del resumen:
    - club_id: identidad histórica ("Real Madrid" a través de los años)
    - team_id: participación concreta (Real Madrid en una temporada/competición)
    """

    club: NamedRef
    team: NamedRef


class PageParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    sort: str | None = Field(
        default=None,
        description="Nombre de campo por el que ordenar. Prefijo '-' para descendente, ej. '-points'.",
    )


class CompetitionFilters(BaseModel):
    """
    Filtros comunes reutilizables en casi cualquier endpoint de stats,
    tal y como se describía en el punto 28-29 del resumen del proyecto.
    """

    edition_id: int | None = None
    competition_id: int | None = None
    competition_phase: str | None = None
    club_id: int | None = None
    team_id: int | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool
