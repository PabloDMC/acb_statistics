from __future__ import annotations

import duckdb

from app.core.exceptions import ResourceNotFoundError
from app.repositories import common_repo, player_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.game_highs import PlayerGameHighs, StatHigh
from app.schemas.match import ShotEvent
from app.schemas.player import (
    PlayerBasicInfo,
    PlayerGameLogEntry,
    PlayerImpact,
    PlayerLineupParticipation,
    PlayerProfile,
    PlayerShootingProfile,
    PlayerSummary,
    PlayerTotals,
)
from app.services.mappers import club_team_ref, competition_context, named_ref, shooting_split


def _totals_from_row(row: dict) -> PlayerTotals:
    return PlayerTotals(
        context=competition_context(row),
        club_team=club_team_ref(row),
        games_played=row.get("games_played"),
        games_started=row.get("games_started"),
        seconds=row.get("seconds"),
        points=row.get("points"),
        assists=row.get("assists"),
        rebounds=row.get("rebounds"),
        steals=row.get("steals"),
        turnovers=row.get("turnovers"),
        blocks=row.get("blocks"),
        personal_fouls=row.get("personal_fouls"),
        fouls_drawn=row.get("fouls_drawn"),
        rating=row.get("rating"),
        field_goals=shooting_split(row, "field_goals"),
        two_pointers=shooting_split(row, "two_pointers"),
        three_pointers=shooting_split(row, "three_pointers"),
        free_throws=shooting_split(row, "free_throws"),
        effective_field_goal_pct=row.get("effective_field_goals_pct"),
        true_shooting_pct=row.get("true_shooting_pct"),
        double_doubles=row.get("double_doubles"),
        triple_doubles=row.get("triple_doubles"),
    )


def _shooting_from_row(row: dict, zones: list[dict]) -> PlayerShootingProfile:
    return PlayerShootingProfile(
        context=competition_context(row),
        club_team=club_team_ref(row),
        field_goals=shooting_split(row, "field_goals"),
        two_pointers=shooting_split(row, "two_pointers"),
        three_pointers=shooting_split(row, "three_pointers"),
        free_throws=shooting_split(row, "free_throws"),
        dunks=shooting_split(row, "dunks"),
        zones=[
            {
                "zone": z["zone"],
                "attempted": z.get("field_goals_attempted"),
                "made": z.get("field_goals_made"),
                "pct": z.get("field_goals_pct"),
                "frequency": z.get("field_goal_frequency"),
            }
            for z in zones
        ],
        assisted_field_goals={
            "assisted_made": row.get("assisted_field_goals_made"),
            "unassisted_made": row.get("unassisted_field_goals_made"),
            "assisted_pct": row.get("assisted_field_goals_pct"),
        },
        assisted_two_pointers_made=row.get("assisted_two_pointers_made"),
        assisted_three_pointers_made=row.get("assisted_three_pointers_made"),
        assisted_dunks=row.get("assisted_dunks"),
        unassisted_dunks=row.get("unassisted_dunks"),
        and_ones=row.get("and_ones"),
    )


def _impact_from_row(row: dict) -> PlayerImpact:
    return PlayerImpact(
        context=competition_context(row),
        on_court_plus_minus_per_100=row.get("on_court_plus_minus_per_100"),
        on_court_offensive_rating=row.get("on_court_offensive_rating"),
        on_court_defensive_rating=row.get("on_court_defensive_rating"),
        on_court_net_rating=row.get("on_court_net_rating"),
        off_court_net_rating=row.get("off_court_net_rating"),
        on_off_net_rating=row.get("on_off_net_rating"),
        possessions_on_court=row.get("possessions_on_court"),
    )


def _synthetic_lineup_id(player_ids: list[int]) -> str:
    return "-".join(str(p) for p in sorted(player_ids))


def _lineup_rows_to_schema(
    rows: list[dict], player_id: int, names_by_id: dict[int, str]
) -> list[PlayerLineupParticipation]:
    result = []
    for row in rows:
        ids = row.get("player_ids") or []
        teammates = [
            {"id": pid, "name": names_by_id.get(pid)}
            for pid in ids
            if pid != player_id
        ]
        result.append(
            PlayerLineupParticipation(
                lineup_id=_synthetic_lineup_id(ids),
                teammates=teammates,
                minutes=row.get("minutes"),
                possessions=row.get("possessions"),
                offensive_rating=row.get("offensive_rating"),
                defensive_rating=row.get("defensive_rating"),
                net_rating=row.get("net_rating"),
                plus_minus=row.get("plus_minus"),
            )
        )
    return result


def list_players(
    cur: duckdb.DuckDBPyConnection,
    name_query: str | None,
    filters: CompetitionFilters,
    page: PageParams,
) -> tuple[list[PlayerSummary], int]:
    rows, total = player_repo.list_players(cur, name_query, filters, page)
    items = [
        PlayerSummary(
            id=row["id"],
            name=row["name"],
            current_team=named_ref(row, "current_team_id", "current_team_name"),
            current_club=(
                {"id": row["current_club_id"], "name": row.get("current_club_name")}
                if row.get("current_club_id") is not None
                else None
            ),
        )
        for row in rows
    ]
    return items, total


def get_basic_info(cur: duckdb.DuckDBPyConnection, player_id: int) -> PlayerBasicInfo:
    row = player_repo.require_basic_info(cur, player_id)
    return PlayerBasicInfo(**row)


def get_totals(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> list[PlayerTotals]:
    player_repo.require_basic_info(cur, player_id)
    rows = player_repo.get_totals(cur, player_id, filters)
    return [_totals_from_row(r) for r in rows]


def get_game_log(
    cur: duckdb.DuckDBPyConnection,
    player_id: int,
    filters: CompetitionFilters,
    page: PageParams,
    include_dnp: bool = False,
) -> tuple[list[PlayerGameLogEntry], int]:
    player_repo.require_basic_info(cur, player_id)
    rows, total = player_repo.get_game_log(cur, player_id, filters, page, include_dnp)
    items = [
        PlayerGameLogEntry(
            match_id=row["match_id"],
            context=competition_context(row),
            opponent=named_ref(row, "opponent_team_id", "opponent_team_name"),
            is_home=row.get("is_home"),
            seconds=row.get("seconds"),
            points=row.get("points"),
            assists=row.get("assists"),
            rebounds=row.get("rebounds"),
            steals=row.get("steals"),
            turnovers=row.get("turnovers"),
            blocks=row.get("blocks"),
            plus_minus=row.get("plus_minus"),
            rating=row.get("rating"),
            field_goals=shooting_split(row, "field_goals"),
            three_pointers=shooting_split(row, "three_pointers"),
            free_throws=shooting_split(row, "free_throws"),
        )
        for row in rows
    ]
    return items, total


def get_shooting_profile(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> list[PlayerShootingProfile]:
    player_repo.require_basic_info(cur, player_id)
    rows = player_repo.get_shooting_profile(cur, player_id, filters)
    zones = player_repo.get_shooting_zones_batch(cur, player_id, filters)
    return [
        _shooting_from_row(row, zones.get(tuple(row.get(k) for k in player_repo._ZONE_KEY), []))
        for row in rows
    ]


def get_impact(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> list[PlayerImpact]:
    player_repo.require_basic_info(cur, player_id)
    return [_impact_from_row(r) for r in player_repo.get_impact(cur, player_id, filters)]


def get_lineup_participations(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters, limit: int = 10
) -> list[PlayerLineupParticipation]:
    player_repo.require_basic_info(cur, player_id)
    rows = player_repo.get_lineup_participations(cur, player_id, filters, limit)

    all_ids = {pid for row in rows for pid in (row.get("player_ids") or [])}
    edition_id = rows[0]["edition_id"] if rows else None
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), edition_id)

    return _lineup_rows_to_schema(rows, player_id, names_by_id)


def get_shots(
    cur: duckdb.DuckDBPyConnection,
    player_id: int,
    filters: CompetitionFilters,
    clutch_only: bool = False,
) -> list[ShotEvent]:
    """
    Lanzamientos de temporada completa (sin agregar), pensado para un shot
    chart de jugador — a diferencia de /matches/{id}/shots, que es de un
    único partido.
    """
    basic = player_repo.require_basic_info(cur, player_id)
    rows = player_repo.get_shots(cur, player_id, filters, clutch_only)
    return [
        ShotEvent(
            player={"id": player_id, "name": basic.get("name")},
            match_id=row.get("match_id"),
            x=row["x"],
            y=row["y"],
            made=row["made"],
            value=row["value"],
            zone=row.get("zone"),
            is_clutch=row.get("is_clutch"),
            quarter=row.get("quarter"),
            seconds_remaining=row.get("seconds_remaining"),
        )
        for row in rows
    ]


def get_game_highs(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> PlayerGameHighs:
    player_repo.require_basic_info(cur, player_id)
    row = player_repo.get_game_highs(cur, player_id, filters)
    # sin partidos en esos filtros: 404 como el perfil, no un 200 con todo a null
    if not row or all(v is None for k, v in row.items() if k.endswith("_value")):
        raise ResourceNotFoundError("player_game_highs_for_filters", {"player_id": player_id, **filters.model_dump()})
    return PlayerGameHighs(**{
        name: StatHigh(value=row.get(f"{name}_value"), match_id=row.get(f"{name}_match_id"))
        for name in PlayerGameHighs.model_fields
    })


def get_profile(
    cur: duckdb.DuckDBPyConnection, player_id: int, filters: CompetitionFilters
) -> PlayerProfile:
    """Endpoint compuesto (BFF) para la página de jugador (punto 32 del resumen)."""
    basic = player_repo.require_basic_info(cur, player_id)

    totals_rows = player_repo.get_totals(cur, player_id, filters)
    shooting_rows = player_repo.get_shooting_profile(cur, player_id, filters)
    shooting_row = shooting_rows[0] if shooting_rows else None
    zones = player_repo.get_shooting_zones(cur, player_id, shooting_row) if shooting_row else []
    impact_rows = player_repo.get_impact(cur, player_id, filters)
    impact_row = impact_rows[0] if impact_rows else None
    lineup_rows = player_repo.get_lineup_participations(cur, player_id, filters, limit=5)

    latest_totals = totals_rows[0] if totals_rows else None

    if latest_totals is None and impact_row is None:
        raise ResourceNotFoundError(
            "player_profile_for_filters", {"player_id": player_id, **filters.model_dump()}
        )

    context_source = latest_totals or impact_row

    all_ids = {pid for row in lineup_rows for pid in (row.get("player_ids") or [])}
    lineup_edition_id = lineup_rows[0]["edition_id"] if lineup_rows else None
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), lineup_edition_id)

    return PlayerProfile(
        player=PlayerBasicInfo(**basic),
        context=competition_context(context_source),
        club_team=club_team_ref(latest_totals) if latest_totals else club_team_ref({}),
        totals=_totals_from_row(latest_totals) if latest_totals else None,
        shooting=_shooting_from_row(shooting_row, zones) if shooting_row else None,
        impact=_impact_from_row(impact_row) if impact_row else None,
        top_lineups=_lineup_rows_to_schema(lineup_rows, player_id, names_by_id),
    )
