from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import NamedRef


class ClubTeamHistoryEntry(BaseModel):
    """Una fila = este club participó como este team_id en esta edición/competición."""

    team: NamedRef
    competition: NamedRef
    edition: NamedRef
