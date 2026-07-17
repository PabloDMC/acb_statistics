import numpy as np
from fastapi import APIRouter
from src.api.app.database import get_connection

router = APIRouter(
    prefix="/players",
    tags=["Players"]
)

@router.get("/")
def get_players():

    conn = get_connection()

    result = conn.execute(
        """
        SELECT DISTINCT
            player_id,
            player_nickname
        FROM main_marts.dim_rosters
        ORDER BY player_nickname
        """
    ).fetchdf()

    conn.close()

    return result.to_dict(orient="records")

@router.get("/{player_id}")
def get_players(player_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT DISTINCT
            player_id,
            player_nickname
        FROM main_marts.dim_rosters
        WHERE player_id = ?
        """,
        [player_id]
    ).fetchdf()

    conn.close()

    return result.to_dict(orient="records")

@router.get("/{player_id}/totals")
def get_players(player_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT *
        FROM main_marts.agg_player_totals
        WHERE player_id = ?
        ORDER BY edition_id, competition_id, competition_phase
        """,
        [player_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{player_id}/games")
def get_players(player_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT dm.match_start_time, dm.round_id, fpg.*
        FROM main_marts.fact_player_games fpg
        LEFT JOIN main_marts.dim_matches dm
        ON fpg.match_id = dm.match_id
        WHERE player_id = ?
        ORDER BY fpg.edition_id, fpg.competition_id, fpg.competition_phase, dm.round_number
        """,
        [player_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{player_id}/game-highs")
def get_players(player_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT 
            player_id,
            max(seconds) as seconds,
            max(points) as points,
            max(free_throws_made) as free_throws_made,
            max(free_throws_attempted) as free_throws_attempted,
            max(two_pointers_made) as two_pointers_made,
            max(two_pointers_attempted) as two_pointers_attempted,
            max(three_pointers_made) as three_pointers_made,
            max(three_pointers_attempted) as three_pointers_attempted,
            max(field_goals_made) as field_goals_made,
            max(field_goals_attempted) as field_goals_attempted,
            max(dunks) as dunks,
            max(assists) as assists,
            max(off_rebounds) as off_rebounds,
            max(def_rebounds) as def_rebounds,
            max(total_rebounds) as total_rebounds,
            max(steals) as steals,
            max(turnovers) as turnovers,
            max(blocks) as blocks,
            max(received_blocks) as received_blocks,
            max(personal_fouls) as personal_fouls,
            max(fouls_drawn) as fouls_drawn,
            max(plus_minus) as plus_minus,
            max(rating) as rating
        FROM main_marts.fact_player_games
        WHERE player_id = ?
        GROUP BY player_id
        """,
        [player_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{player_id}/shooting")
def get_players(player_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT *
        FROM main_marts.agg_player_shooting
        WHERE player_id = ?
        ORDER BY edition_id, competition_id, competition_phase
        """,
        [player_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{player_id}/shooting-zones")
def get_players(player_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT *
        FROM main_marts.agg_player_shooting_zones
        WHERE player_id = ?
        ORDER BY edition_id, competition_id, competition_phase
        """,
        [player_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{player_id}/lineups")
def get_players(player_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT *
        FROM main_marts.agg_lineup_combinations
        WHERE player_count = 5
        AND ? IN player_ids
        ORDER BY edition_id, competition_id, competition_phase
        """,
        [player_id]
    ).fetchdf()
    
    conn.close()
    
    #result["player_ids"] = result["player_ids"].apply(list)
    result = result.astype(object)
    return result.replace({np.nan: None}).to_dict(orient="records")