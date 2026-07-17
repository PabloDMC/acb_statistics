import numpy as np
from fastapi import APIRouter
from src.api.app.database import get_connection

router = APIRouter(
    prefix="/teams",
    tags=["Teams"]
)

@router.get("/")
def get_teams():

    conn = get_connection()

    result = conn.execute(
        """
        SELECT DISTINCT
            team_id,
            club_id,
            edition_id,
            competition_id,
            full_name,
            short_name,
            abbr,
            logo,
            secondary_logo,
            primary_color,
            text_color
        FROM main_marts.dim_teams
        ORDER BY club_id,edition_id,competition_id
        """
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{team_id}")
def get_teams(team_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT DISTINCT
            team_id,
            club_id,
            edition_id,
            competition_id,
            full_name,
            short_name,
            abbr,
            logo,
            secondary_logo,
            primary_color,
            text_color
        FROM main_marts.dim_teams
        WHERE club_id = ?
        ORDER BY club_id,edition_id,competition_id
        """,
        [team_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{team_id}/totals")
def get_teams(team_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT *
        FROM main_marts.agg_team_totals
        WHERE team_id = ?
        ORDER BY edition_id, competition_id, competition_phase
        """,
        [team_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")

@router.get("/{team_id}/games")
def get_teams(team_id: int):

    conn = get_connection()

    result = conn.execute(
        """
        SELECT dm.match_start_time, dm.round_id, ftg.*
        FROM main_marts.fact_team_games ftg
        LEFT JOIN main_marts.dim_matches dm
        ON ftg.match_id = dm.match_id
        WHERE club_id = ?
        ORDER BY ftg.edition_id, ftg.competition_id, ftg.competition_phase, dm.round_number
        """,
        [team_id]
    ).fetchdf()

    conn.close()

    return result.replace({np.nan: None}).to_dict(orient="records")