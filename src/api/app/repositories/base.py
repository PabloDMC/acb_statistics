"""
Utilidades compartidas por todos los repositorios: construir la parte de
WHERE a partir de `CompetitionFilters`, aplicar orden y paginación de forma
consistente. Todo repositorio SQL-específico se apoya en esto en lugar de
reinventar el parseo de filtros en cada función.
"""

from __future__ import annotations

from app.schemas.common import CompetitionFilters, PageParams


class SQLFilterBuilder:
    """
    Construye cláusulas WHERE parametrizadas para DuckDB a partir de los
    filtros comunes (edition_id, competition_id, competition_phase, club_id,
    team_id). Usa siempre placeholders (?) para evitar inyección SQL.
    """

    def __init__(self, table_alias: str = ""):
        self._prefix = f"{table_alias}." if table_alias else ""
        self.clauses: list[str] = []
        self.params: list[object] = []

    def add(self, condition_field: str, value: object | None) -> "SQLFilterBuilder":
        if value is not None:
            self.clauses.append(f"{self._prefix}{condition_field} = ?")
            self.params.append(value)
        return self

    def add_competition_filters(self, filters: CompetitionFilters) -> "SQLFilterBuilder":
        self.add("edition_id", filters.edition_id)
        self.add("competition_id", filters.competition_id)
        self.add("competition_phase", filters.competition_phase)
        self.add("club_id", filters.club_id)
        self.add("team_id", filters.team_id)
        return self

    def where_sql(self) -> str:
        if not self.clauses:
            return ""
        return "WHERE " + " AND ".join(self.clauses)


# Columnas por las que cada endpoint permite ordenar. Es una allow-list a
# propósito: `sort` viene de query params del usuario y jamás debe
# interpolarse directamente en SQL sin validar contra esta lista.
def resolve_sort(sort: str | None, allowed_columns: set[str], default: str) -> tuple[str, str]:
    if not sort:
        return default, "DESC"

    direction = "ASC"
    column = sort
    if sort.startswith("-"):
        direction = "DESC"
        column = sort[1:]

    if column not in allowed_columns:
        column = default
        direction = "DESC"

    return column, direction


def pagination_sql(page: PageParams) -> str:
    return f"LIMIT {int(page.limit)} OFFSET {int(page.offset)}"
