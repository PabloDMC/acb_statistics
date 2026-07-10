{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

SELECT

    match_id,

    edition_id,
    competition_id,

    week_id,

    match_start_time,

    attendance,

    ---------------------------------------------------
    -- Competición
    ---------------------------------------------------

    round_type,
    round_id,
    round_number,

    group_id,

    subphase_id,
    subphase_number,

    match_grouping,

    ---------------------------------------------------
    -- Equipos
    ---------------------------------------------------

    home_team_id,
    away_team_id,
    current_home_score AS home_score,
    current_away_score AS away_score,

    ---------------------------------------------------
    -- Staff
    ---------------------------------------------------

    home_head_coach,
    away_head_coach,

    home_assistant_coaches,
    away_assistant_coaches,

    ---------------------------------------------------
    -- Arena
    ---------------------------------------------------

    home_arena,
    away_arena,

    ---------------------------------------------------
    -- Árbitros
    ---------------------------------------------------

    referees,

    cat_insert_date

FROM {{ ref('int_matches') }}