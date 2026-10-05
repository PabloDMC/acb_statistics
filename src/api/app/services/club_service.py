from __future__ import annotations

import duckdb

from app.repositories import club_repo
from app.schemas.club import ClubTeamHistoryEntry


def get_team_history(cur: duckdb.DuckDBPyConnection, club_id: int) -> list[ClubTeamHistoryEntry]:
    rows = club_repo.list_teams_for_club(cur, club_id)
    return [
        ClubTeamHistoryEntry(
            team={"id": row["team_id"], "name": row.get("team_name")},
            competition={"id": row.get("competition_id"), "name": row.get("competition_name")},
            edition={"id": row.get("edition_id"), "name": row.get("edition_name")},
        )
        for row in rows
    ]
