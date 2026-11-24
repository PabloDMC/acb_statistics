from __future__ import annotations

import duckdb

from app.repositories import common_repo, match_repo
from app.schemas.common import CompetitionFilters, PageParams
from app.schemas.match import (
    Boxscore,
    BoxscorePlayer,
    BoxscoreTeam,
    LineupStint,
    MatchSummary,
    PlayByPlayEvent,
    QuarterScore,
    ShotEvent,
)
from app.services.mappers import competition_context


def _match_to_schema(row: dict) -> MatchSummary:
    return MatchSummary(
        id=row["id"],
        context=competition_context(row),
        date=row.get("date").isoformat() if hasattr(row.get("date"), "isoformat") else row.get("date"),
        home_team={"id": row["home_team_id"], "name": row.get("home_team_name")},
        away_team={"id": row["away_team_id"], "name": row.get("away_team_name")},
        home_score=row.get("home_score"),
        away_score=row.get("away_score"),
        venue=row.get("venue"),
        round=row.get("round_number"),
        status=row.get("status"),
        is_played=row.get("is_played"),
        has_boxscore=row.get("has_boxscore"),
        has_play_by_play=row.get("has_play_by_play"),
        has_shots=row.get("has_shots"),
        attendance=row.get("attendance"),
        home_coach=row.get("home_head_coach"),
        away_coach=row.get("away_head_coach"),
        referees=_parse_referees(row.get("referees")),
        home_team_logo=row.get("home_team_logo"),
        away_team_logo=row.get("away_team_logo"),
    )


def _parse_referees(value) -> list[str]:
    """`referees` llega como texto de una lista ("[A, B, C]") o como lista."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    text = str(value).strip().strip("[]")
    return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]


def shot_from_row(row: dict, player_name: str | None, match_infos: dict | None = None) -> ShotEvent:
    """Fila de fact_shots -> ShotEvent (compartido por partido, jugador y equipo). Con
    `match_infos` (common_repo.match_info_batch) añade fecha y rival."""
    match_id = row.get("match_id") or row.get("shot_match_id")
    ctx = common_repo.match_context_for_team((match_infos or {}).get(match_id), row.get("team_id"))
    score = None
    if row.get("score_team") is not None and row.get("score_opp") is not None:
        score = f"{row['score_team']}-{row['score_opp']}"
    return ShotEvent(
        player={"id": row.get("player_id"), "name": player_name},
        team_id=row.get("team_id"),
        match_id=match_id,
        date=ctx.get("date"),
        opponent=ctx.get("opponent"),
        score=score,
        x=row["x"],
        y=row["y"],
        made=row["made"],
        value=row["value"],
        zone_id=row.get("zone_id"),
        zone=row.get("zone"),
        area=row.get("area"),
        range=row.get("range"),
        is_clutch=row.get("is_clutch"),
        quarter=row.get("quarter"),
        seconds_remaining=row.get("seconds_remaining"),
    )


def get_match(cur: duckdb.DuckDBPyConnection, match_id: int) -> MatchSummary:
    row = match_repo.require_match(cur, match_id)
    return _match_to_schema(row)


def list_matches(
    cur: duckdb.DuckDBPyConnection,
    filters: CompetitionFilters,
    page: PageParams,
    round_number: int | None = None,
    opponent_team_id: int | None = None,
    opponent_club_id: int | None = None,
) -> tuple[list[MatchSummary], int]:
    rows, total = match_repo.list_matches(cur, filters, page, round_number, opponent_team_id, opponent_club_id)
    return [_match_to_schema(r) for r in rows], total


def get_shots(
    cur: duckdb.DuckDBPyConnection,
    match_id: int,
    team_id: int | None,
    player_id: int | None,
    clutch_only: bool = False,
) -> list[ShotEvent]:
    match = match_repo.require_match(cur, match_id)
    rows = match_repo.get_shots(cur, match_id, team_id, player_id, clutch_only)

    all_ids = {row["player_id"] for row in rows if row.get("player_id") is not None}
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), match.get("edition_id"))

    infos = common_repo.match_info_batch(cur, [match_id])
    return [shot_from_row(row, names_by_id.get(row["player_id"]), infos) for row in rows]


def get_lineup_stints(cur: duckdb.DuckDBPyConnection, match_id: int) -> list[LineupStint]:
    match = match_repo.require_match(cur, match_id)
    rows = match_repo.get_lineup_stints(cur, match_id)

    all_ids = {pid for row in rows for pid in (row.get("player_ids") or [])}
    names_by_id = common_repo.player_names_batch(cur, list(all_ids), match.get("edition_id"))

    return [
        LineupStint(
            team={"id": row["team_id"], "name": row.get("team_full_name")},
            quarter=row.get("quarter"),
            start_time=row.get("start_time"),
            end_time=row.get("end_time"),
            players=[
                {"id": pid, "name": names_by_id.get(pid)}
                for pid in (row.get("player_ids") or [])
            ],
            team_points=row.get("team_points"),
            opponent_points=row.get("opp_points"),
            plus_minus=row.get("plus_minus"),
            offensive_possessions=row.get("offensive_possessions"),
            defensive_possessions=row.get("defensive_possessions"),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Boxscore y jugada a jugada
# ---------------------------------------------------------------------------

_BOX_PLAYER_STATS = [
    "points",
    "field_goals_made", "field_goals_attempted",
    "two_pointers_made", "two_pointers_attempted",
    "three_pointers_made", "three_pointers_attempted",
    "free_throws_made", "free_throws_attempted",
    "off_rebounds", "def_rebounds", "total_rebounds",
    "assists", "steals", "turnovers", "blocks", "received_blocks", "dunks",
    "personal_fouls", "fouls_drawn", "plus_minus", "rating",
]


def _quarter_box(cur, match_id: int, quarter: int, players: list[dict]) -> tuple[list[dict], dict]:
    """Sustituye las líneas del partido por las del cuarto (jugada a jugada + tramos). Los
    totales de equipo son la suma de sus jugadores (sin rebotes ni pérdidas de equipo)."""
    qbox = match_repo.get_quarter_box(cur, match_id, quarter)
    out = []
    for p in players:
        q = qbox.get(p["player_id"], {})
        sec = q.get("seconds") or 0
        row = {k: p.get(k) for k in ("team_id", "player_id", "player_name", "shirt_number", "position", "is_starter")}
        row.update({c: q.get(c, 0) or 0 for c in _BOX_PLAYER_STATS if c not in ("rating",)})
        row["rating"] = None
        row["seconds"] = sec
        row["play_time"] = f"{sec // 60:d}:{sec % 60:02d}" if sec else None
        out.append(row)
    teams: dict[int, dict] = {}
    for r in out:
        t = teams.setdefault(r["team_id"], {c: 0 for c in _BOX_PLAYER_STATS if c not in ("plus_minus", "rating")})
        for c in t:
            t[c] += r.get(c) or 0
    return out, teams


def get_boxscore(cur: duckdb.DuckDBPyConnection, match_id: int, quarter: int | None = None) -> Boxscore:
    match_row = match_repo.require_match(cur, match_id)
    match = _match_to_schema(match_row)
    players = match_repo.get_boxscore_players(cur, match_id)
    teams = {t["team_id"]: t for t in match_repo.get_boxscore_teams(cur, match_id)}
    if quarter is not None:
        players, teams = _quarter_box(cur, match_id, quarter, players)

    # parciales por cuarto a partir del marcador acumulado
    quarters, prev_h, prev_a = [], 0, 0
    for q in match_repo.get_quarter_scores(cur, match_id):
        h, a = q.get("home"), q.get("away")
        quarters.append(QuarterScore(
            quarter=q["quarter"],
            home=None if h is None else h - prev_h,
            away=None if a is None else a - prev_a,
        ))
        prev_h, prev_a = h or prev_h, a or prev_a

    def team_box(team_id: int, team_name: str | None, coach: str | None) -> BoxscoreTeam:
        totals = dict(teams.get(team_id, {}))
        for k in ("team_id", "is_home"):
            totals.pop(k, None)
        return BoxscoreTeam(
            team={"id": team_id, "name": team_name},
            coach=coach,
            players=[
                BoxscorePlayer(
                    player={"id": p["player_id"], "name": p.get("player_name")},
                    shirt_number=p.get("shirt_number"),
                    position=p.get("position"),
                    is_starter=p.get("is_starter"),
                    played=bool(p.get("seconds")),
                    seconds=p.get("seconds"),
                    minutes=p.get("play_time"),
                    stats={c: p.get(c) for c in _BOX_PLAYER_STATS},
                )
                for p in players
                if p["team_id"] == team_id
            ],
            totals=totals,
        )

    return Boxscore(
        match=match,
        quarters=quarters,
        home=team_box(match_row["home_team_id"], match_row.get("home_team_name"), match_row.get("home_head_coach")),
        away=team_box(match_row["away_team_id"], match_row.get("away_team_name"), match_row.get("away_head_coach")),
    )


def get_play_by_play(
    cur: duckdb.DuckDBPyConnection, match_id: int, quarter: int | None, include_system: bool
) -> list[PlayByPlayEvent]:
    match = match_repo.require_match(cur, match_id)
    rows = match_repo.get_play_by_play(cur, match_id, quarter, include_system)
    ids = [r["player_id"] for r in rows if r.get("player_id") is not None]
    names = common_repo.player_names_batch(cur, ids, match.get("edition_id"))
    team_names = {
        match["home_team_id"]: match.get("home_team_name"),
        match["away_team_id"]: match.get("away_team_name"),
    }

    def clock(sec):
        return None if sec is None else f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"

    return [
        PlayByPlayEvent(
            event_idx=r["event_idx"],
            quarter=r["quarter"],
            clock=clock(r.get("seconds_remaining")),
            seconds_remaining=r.get("seconds_remaining"),
            play_type_id=r.get("play_type_id"),
            play=r.get("play_name"),
            category=r.get("play_category"),
            sub_category=r.get("play_sub_category"),
            team=None if r.get("team_id") is None else {"id": r["team_id"], "name": team_names.get(r["team_id"])},
            player=None if r.get("player_id") is None else {"id": r["player_id"], "name": names.get(r["player_id"])},
            points=r.get("points"),
            score_home=r.get("score_home"),
            score_away=r.get("score_away"),
            is_clutch=r.get("is_clutch"),
            possession_id=r.get("possession_id"),
            offense_team_id=r.get("offense_team_id"),
            event_kind=r.get("event_kind") or None,
        )
        for r in rows
    ]
