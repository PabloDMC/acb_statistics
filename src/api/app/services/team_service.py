from __future__ import annotations

import duckdb

from app.core.exceptions import ResourceNotFoundError
from app.repositories import common_repo, team_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.game_highs import StatHigh, TeamGameHighs
from app.schemas.match import ShotEvent
from app.schemas.team import (
    LineupCombination,
    PlayerRotation,
    RotationMinute,
    TeamGameLogEntry,
    TeamRotations,
    TeamSummary,
    TeamTotals,
)
from app.services import match_service
from app.services.mappers import club_team_ref, competition_context, named_ref, shooting_split  # noqa: F401


def list_teams(
    cur: duckdb.DuckDBPyConnection,
    name_query: str | None,
    filters: CompetitionFilters,
    page: PageParams,
) -> tuple[list[TeamSummary], int]:
    rows, total = team_repo.list_teams(cur, name_query, filters, page)
    items = [
        TeamSummary(
            team={"id": row["id"], "name": row["name"]},
            club={"id": row.get("club_id"), "name": row.get("club_name")},
        )
        for row in rows
    ]
    return items, total


def get_totals(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters
) -> list[TeamTotals]:
    team_repo.require_basic_info(cur, team_id)
    rows = team_repo.get_totals(cur, team_id, filters)
    return [
        TeamTotals(
            context=competition_context(row),
            club_team=club_team_ref(row),
            games_played=row.get("games_played"),
            wins=row.get("wins"),
            losses=row.get("losses"),
            points_for=row.get("points_for"),
            points_against=row.get("points_against"),
            possessions=row.get("possessions"),
            offensive_rating=row.get("offensive_rating"),
            defensive_rating=row.get("defensive_rating"),
            net_rating=row.get("net_rating"),
            stats={c: row.get(c) for c in team_repo._TEAM_STAT_COLUMNS},
        )
        for row in rows
    ]


def get_game_log(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters, page: PageParams
) -> tuple[list[TeamGameLogEntry], int]:
    team_repo.require_basic_info(cur, team_id)
    rows, total = team_repo.get_game_log(cur, team_id, filters, page)
    items = [
        TeamGameLogEntry(
            match_id=row["match_id"],
            context=competition_context(row),
            opponent=named_ref(row, "opponent_team_id", "opponent_team_name"),
            is_home=row.get("is_home"),
            result=row.get("result"),
            points_for=row.get("points_for"),
            points_against=row.get("points_against"),
            possessions=row.get("possessions"),
            offensive_rating=row.get("offensive_rating"),
            defensive_rating=row.get("defensive_rating"),
            net_rating=row.get("net_rating"),
        )
        for row in rows
    ]
    return items, total


def get_lineup_combinations(
    cur: duckdb.DuckDBPyConnection,
    team_id: int,
    filters: CompetitionFilters,
    combination_size: int | None,
    page: PageParams,
) -> tuple[list[LineupCombination], int]:
    team_repo.require_basic_info(cur, team_id)
    rows, total = team_repo.get_lineup_combinations(cur, team_id, filters, combination_size, page)

    # agg_lineup_combinations no trae nombres de jugador: se resuelven en lote.
    all_ids = {pid for row in rows for pid in (row.get("player_ids") or [])}
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), filters.edition_id)

    items = [
        LineupCombination(
            combination_size=row["combination_size"],
            players=[
                {"id": pid, "name": names_by_id.get(pid)}
                for pid in (row.get("player_ids") or [])
            ],
            minutes=row.get("minutes"),
            possessions=row.get("possessions"),
            offensive_rating=row.get("offensive_rating"),
            defensive_rating=row.get("defensive_rating"),
            net_rating=row.get("net_rating"),
            plus_minus=row.get("plus_minus"),
        )
        for row in rows
    ]
    return items, total


def get_game_highs(
    cur: duckdb.DuckDBPyConnection, team_id: int, filters: CompetitionFilters
) -> TeamGameHighs:
    team_repo.require_basic_info(cur, team_id)
    row = team_repo.get_game_highs(cur, team_id, filters)
    # sin partidos en esos filtros: 404 como el perfil, no un 200 con todo a null
    if not row or all(v is None for k, v in row.items() if k.endswith("_value")):
        raise ResourceNotFoundError("team_game_highs_for_filters", {"team_id": team_id, **filters.model_dump()})
    return TeamGameHighs(**{
        name: StatHigh(value=row.get(f"{name}_value"), match_id=row.get(f"{name}_match_id"))
        for name in TeamGameHighs.model_fields
    })


def get_shots(
    cur: duckdb.DuckDBPyConnection,
    team_id: int,
    side: str,
    competition_phase: str | None,
    clutch_only: bool,
) -> list[ShotEvent]:
    info = team_repo.require_basic_info(cur, team_id)
    rows = team_repo.get_shots(cur, team_id, side, competition_phase, clutch_only)
    ids = [r["player_id"] for r in rows if r.get("player_id") is not None]
    names = common_repo.player_names_batch(cur, ids, info.get("edition_id"))
    return [match_service.shot_from_row(r, names.get(r.get("player_id"))) for r in rows]


def get_rotations(
    cur: duckdb.DuckDBPyConnection, team_id: int, competition_phase: str | None
) -> TeamRotations:
    info = team_repo.require_basic_info(cur, team_id)
    rows = team_repo.get_rotations(cur, team_id, competition_phase)
    if not rows:
        raise ResourceNotFoundError("team_rotations", {"team_id": team_id, "competition_phase": competition_phase})

    # Varias fases (liga + playoffs) se suman: partidos del equipo = suma por fase
    team_games = sum({r["competition_phase"]: r["team_games"] for r in rows}.values())
    player_games: dict[int, dict[str, int]] = {}
    per_minute: dict[int, dict[int, list[int]]] = {}
    for r in rows:
        player_games.setdefault(r["player_id"], {})[r["competition_phase"]] = r["player_games"]
        cell = per_minute.setdefault(r["player_id"], {}).setdefault(r["minute"], [0, 0])
        cell[0] += r["games_on_court"]
        cell[1] += r["seconds_on_court"]

    names = common_repo.player_names_batch(cur, list(per_minute), info.get("edition_id"))
    players = []
    for pid, minutes in per_minute.items():
        players.append(PlayerRotation(
            player={"id": pid, "name": names.get(pid)},
            player_games=sum(player_games[pid].values()),
            total_seconds=sum(c[1] for c in minutes.values()),
            minutes=[
                RotationMinute(
                    minute=m,
                    games_on_court=minutes.get(m, [0, 0])[0],
                    pct_games_on_court=minutes.get(m, [0, 0])[0] / team_games if team_games else None,
                    avg_seconds=minutes.get(m, [0, 0])[1] / team_games if team_games else None,
                )
                for m in range(40)
            ],
        ))
    players.sort(key=lambda p: p.total_seconds, reverse=True)
    return TeamRotations(
        team={"id": team_id, "name": info.get("full_name") or info.get("name") or info.get("team_name")},
        team_games=team_games,
        players=players,
    )
