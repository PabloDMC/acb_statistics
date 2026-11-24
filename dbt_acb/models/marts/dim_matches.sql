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
    match_status,
    is_played,

    ---------------------------------------------------
    -- Cobertura: qué datos tiene el partido. Antes de 2016-17 la ACB solo ofrece el boxscore
    -- final (sin cuartos), y algunos partidos antiguos ni eso: solo el resultado.
    ---------------------------------------------------
    match_id IN (SELECT match_id FROM {{ ref('stg_apiacb__boxscore') }}) AS has_boxscore,
    match_id IN (SELECT match_id FROM {{ ref('stg_apiacb__play_by_play') }}) AS has_play_by_play,
    match_id IN (SELECT match_id FROM {{ ref('stg_apiacb__match_shots') }}) AS has_shots,

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

FROM {{ ref('int_matches') }} m