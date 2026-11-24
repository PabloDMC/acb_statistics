from __future__ import annotations

from collections import Counter, defaultdict
from itertools import groupby

import duckdb

from app.core.exceptions import ResourceNotFoundError
from app.repositories import season_repo
from app.schemas.season import (
    CompetitionInfo,
    Coverage,
    EditionInfo,
    LeagueZone,
    PhaseInfo,
    RoundPosition,
    SearchHit,
    SearchResults,
    StandingRow,
    Standings,
    StandingsHistory,
    StandingsRound,
)

PHASE_NAMES = {
    "LR": "Liga regular",
    "PO": "Playoffs",
    "CR": "Copa del Rey",
    "SC": "Supercopa",
}

TIEBREAK = (
    "Victorias; entre empatados, victorias en sus enfrentamientos directos, luego basket-average "
    "particular (diferencia de puntos en esos partidos), basket-average general y puntos a favor. "
    "Si tras los enfrentamientos directos siguen empatados varios, se repite el criterio entre ellos."
)


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

def list_editions(cur: duckdb.DuckDBPyConnection) -> list[EditionInfo]:
    rows = season_repo.list_editions(cur)
    editions: list[EditionInfo] = []
    for edition_id, ed_rows in groupby(rows, key=lambda r: r["edition_id"]):
        ed_rows = list(ed_rows)
        comps = []
        for comp_id, c_rows in groupby(ed_rows, key=lambda r: r["competition_id"]):
            c_rows = list(c_rows)
            played = sum(r.get("played") or 0 for r in c_rows)
            with_pbp = sum(r.get("with_play_by_play") or 0 for r in c_rows)
            with_shots = sum(r.get("with_shots") or 0 for r in c_rows)
            comps.append(CompetitionInfo(
                id=comp_id,
                name=c_rows[0].get("competition_name"),
                coverage=Coverage(
                    played=played,
                    with_boxscore=sum(r.get("with_boxscore") or 0 for r in c_rows),
                    with_play_by_play=with_pbp,
                    with_shots=with_shots,
                    has_play_by_play=played > 0 and with_pbp * 2 >= played,
                    has_shots=played > 0 and with_shots * 2 >= played,
                ),
                phases=[
                    PhaseInfo(
                        code=r["phase"],
                        name=PHASE_NAMES.get(r["phase"]),
                        matches=r["matches"],
                        first_date=_iso(r.get("first_date")),
                        last_date=_iso(r.get("last_date")),
                    )
                    for r in c_rows
                ],
            ))
        editions.append(EditionInfo(
            id=edition_id,
            name=ed_rows[0].get("edition_name"),
            start_year=ed_rows[0].get("start_year"),
            competitions=comps,
        ))
    return editions


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------

def _team_records(games: list[dict]) -> dict[int, dict]:
    rec: dict[int, dict] = defaultdict(lambda: {
        "games": 0, "wins": 0, "losses": 0, "points_for": 0, "points_against": 0,
        "home_wins": 0, "home_losses": 0, "away_wins": 0, "away_losses": 0, "results": [],
    })
    for g in games:  # ya vienen en orden cronológico
        r = rec[g["team_id"]]
        win = g["points"] > g["opponent_points"]
        r["games"] += 1
        r["wins"] += win
        r["losses"] += not win
        r["points_for"] += g["points"]
        r["points_against"] += g["opponent_points"]
        side = "home" if g["is_home"] else "away"
        r[f"{side}_{'wins' if win else 'losses'}"] += 1
        r["results"].append("G" if win else "P")
    return rec


def _order_tied(team_ids: list[int], games: list[dict], rec: dict[int, dict]) -> list[int]:
    """Desempate oficial entre equipos igualados a victorias (recursivo)."""
    if len(team_ids) <= 1:
        return list(team_ids)
    group = set(team_ids)
    h2h = {t: [0, 0] for t in team_ids}  # victorias, diferencia de puntos en los directos
    for g in games:
        if g["team_id"] in group and g["opponent_team_id"] in group:
            h2h[g["team_id"]][0] += g["points"] > g["opponent_points"]
            h2h[g["team_id"]][1] += g["points"] - g["opponent_points"]

    key = lambda t: (h2h[t][0], h2h[t][1])  # noqa: E731
    ordered = sorted(team_ids, key=key, reverse=True)
    buckets = [list(b) for _, b in groupby(ordered, key=key)]

    if len(buckets) == 1:
        # los directos no separan a nadie: basket-average general y puntos a favor
        return sorted(
            team_ids,
            key=lambda t: (rec[t]["points_for"] - rec[t]["points_against"], rec[t]["points_for"]),
            reverse=True,
        )
    result: list[int] = []
    for bucket in buckets:
        result.extend(_order_tied(bucket, games, rec))  # se repite el criterio entre los que siguen empatados
    return result


IRREGULAR_TIEBREAK = (
    "Porcentaje de victorias y, a igualdad, diferencia de puntos. La fase regular de esta temporada "
    "no fue una liga a doble vuelta (se jugó en grupos o en varias fases), así que esta tabla es el "
    "balance de cada equipo en toda la fase, no la clasificación oficial."
)


def is_double_round_robin(games: list[dict]) -> bool:
    """Liga a doble vuelta: cada equipo se enfrenta exactamente dos veces a todos los demás.
    En las temporadas antiguas la fase regular se jugaba en grupos o en varias fases (la API no
    distingue los grupos), y ahí una clasificación única con desempates oficiales no tiene sentido."""
    meetings: dict[int, Counter] = defaultdict(Counter)
    for g in games:
        meetings[g["team_id"]][g["opponent_team_id"]] += 1
    teams = set(meetings)
    return len(teams) > 1 and all(
        set(opp) == teams - {t} and all(n == 2 for n in opp.values()) for t, opp in meetings.items()
    )


def _rank(games: list[dict], official: bool = True) -> tuple[list[int], dict[int, dict]]:
    rec = _team_records(games)
    if not official:
        order = sorted(rec, key=lambda t: (
            -(rec[t]["wins"] / rec[t]["games"]) if rec[t]["games"] else 0,
            -(rec[t]["points_for"] - rec[t]["points_against"]),
        ))
        return order, rec
    by_record = sorted(rec, key=lambda t: (-rec[t]["wins"], rec[t]["losses"]))
    order: list[int] = []
    for _, tied in groupby(by_record, key=lambda t: (rec[t]["wins"], rec[t]["losses"])):
        order.extend(_order_tied(list(tied), games, rec))
    return order, rec


def _streak(results: list[str]) -> str | None:
    if not results:
        return None
    last = results[-1]
    n = 0
    for r in reversed(results):
        if r != last:
            break
        n += 1
    return f"{last}{n}"


def _rows(order: list[int], rec: dict[int, dict], info: dict[int, dict]) -> list[StandingRow]:
    rows = []
    for pos, team_id in enumerate(order, start=1):
        r = rec[team_id]
        t = info.get(team_id, {})
        rows.append(StandingRow(
            position=pos,
            team={"id": team_id, "name": t.get("team_name")},
            club={"id": t.get("club_id"), "name": t.get("club_name")},
            abbr=t.get("abbr"),
            logo=t.get("logo"),
            games=r["games"],
            wins=r["wins"],
            losses=r["losses"],
            win_pct=r["wins"] / r["games"] if r["games"] else None,
            points_for=r["points_for"],
            points_against=r["points_against"],
            point_diff=r["points_for"] - r["points_against"],
            home_wins=r["home_wins"],
            home_losses=r["home_losses"],
            away_wins=r["away_wins"],
            away_losses=r["away_losses"],
            streak=_streak(r["results"]),
            last5="".join(r["results"][-5:]) or None,
        ))
    return rows


def _context(cur, edition_id: int, competition_id: int, phase: str) -> dict:
    names = season_repo.context_names(cur, edition_id, competition_id)
    return {
        "competition": {"id": competition_id, "name": names.get("competition_name")},
        "edition": {"id": edition_id, "name": names.get("edition_name")},
        "competition_phase": phase,
    }


def _is_current_or_round_robin(cur, edition_id: int, competition_id: int, games: list[dict]) -> bool:
    """Doble vuelta, o temporada en curso (con partidos aún por jugar no se puede comprobar;
    las actuales siempre son a doble vuelta)."""
    if is_double_round_robin(games):
        return True
    return season_repo.has_pending_matches(cur, edition_id, competition_id)


def _games_or_404(cur, edition_id: int, competition_id: int, phase: str) -> list[dict]:
    games = season_repo.standings_games(cur, edition_id, competition_id, phase)
    if not games:
        raise ResourceNotFoundError(
            "standings",
            {"edition_id": edition_id, "competition_id": competition_id, "competition_phase": phase},
        )
    return games


def get_standings(
    cur: duckdb.DuckDBPyConnection,
    edition_id: int,
    competition_id: int,
    competition_phase: str,
    round_number: int | None,
) -> Standings:
    games = _games_or_404(cur, edition_id, competition_id, competition_phase)
    # el formato se decide con la fase entera (a mitad de temporada aún no hay doble vuelta)
    official = competition_phase != "LR" or _is_current_or_round_robin(cur, edition_id, competition_id, games)
    if round_number is not None:
        games = [g for g in games if g.get("round_number") is not None and g["round_number"] <= round_number]
    order, rec = _rank(games, official)
    info = season_repo.teams_info(cur, order)
    return Standings(
        context=_context(cur, edition_id, competition_id, competition_phase),
        round=round_number,
        official=official,
        tiebreak=TIEBREAK if official else IRREGULAR_TIEBREAK,
        rows=_rows(order, rec, info),
    )


def get_standings_history(
    cur: duckdb.DuckDBPyConnection,
    edition_id: int,
    competition_id: int,
    competition_phase: str,
) -> StandingsHistory:
    games = _games_or_404(cur, edition_id, competition_id, competition_phase)
    official = competition_phase != "LR" or _is_current_or_round_robin(cur, edition_id, competition_id, games)
    rounds = sorted({g["round_number"] for g in games if g.get("round_number") is not None})
    history = []
    for rnd in rounds:
        order, rec = _rank([g for g in games if g.get("round_number") is not None and g["round_number"] <= rnd], official)
        history.append(StandingsRound(
            round=rnd,
            positions=[
                RoundPosition(team_id=t, position=i, wins=rec[t]["wins"], losses=rec[t]["losses"])
                for i, t in enumerate(order, start=1)
            ],
        ))
    order, rec = _rank(games, official)
    info = season_repo.teams_info(cur, order)
    return StandingsHistory(
        context=_context(cur, edition_id, competition_id, competition_phase),
        official=official,
        teams=_rows(order, rec, info),
        rounds=history,
    )


# ---------------------------------------------------------------------------
# Liga y búsqueda
# ---------------------------------------------------------------------------

def league_shot_zones(cur: duckdb.DuckDBPyConnection, edition_id: int | None) -> list[LeagueZone]:
    return [LeagueZone(**r) for r in season_repo.league_shot_zones(cur, edition_id)]


def search(cur: duckdb.DuckDBPyConnection, q: str, limit: int) -> SearchResults:
    res = season_repo.search(cur, q.strip(), limit)
    return SearchResults(
        query=q,
        players=[SearchHit(type="player", **r) for r in res["players"]],
        clubs=[SearchHit(type="club", **r) for r in res["clubs"]],
        teams=[SearchHit(type="team", **r) for r in res["teams"]],
    )
