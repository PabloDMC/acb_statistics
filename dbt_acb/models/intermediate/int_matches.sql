{{ config(
    materialized='table',
    schema = "intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'competition_id', 'match_id']
) }}

-- Una fila por partido del calendario (matchlist), jugado o no. Los partidos aún sin cabecera
-- (programados) toman fecha, equipos y marcador del propio calendario; is_played distingue los
-- terminados, que son los únicos que cuentan en estadísticas y clasificación.
WITH mh AS (
    SELECT *
    FROM {{ ref('stg_apiacb__match_header') }}
),

ml AS (
    SELECT *
    FROM {{ ref('stg_apiacb__matchlist') }}
),

bs AS (
    SELECT DISTINCT
        match_id,
        team_id,
        edition_id,
        try_cast(head_coach AS VARCHAR) AS head_coach,
        try_cast(assistant_coaches AS VARCHAR) AS assistant_coaches,
        try_cast(arena AS VARCHAR) AS arena,
        try_cast(attendance AS INT) AS attendance,
        try_cast(referees AS VARCHAR) AS referees
    FROM {{ ref('stg_apiacb__boxscore') }}
)

SELECT
    ml.match_id,
    ml.edition_id,
    coalesce(mh.competition_id, ml.competition_id) AS competition_id,
    ml.week_id,

    coalesce(mh.match_start_time, ml.match_start_time) AS match_start_time,
    coalesce(mh.match_status, ml.match_status) AS match_status,
    mh.is_on_half_time,
    mh.time_left,
    mh.current_quarter,
    coalesce(mh.current_home_score, ml.home_score) AS current_home_score,
    coalesce(mh.current_away_score, ml.away_score) AS current_away_score,
    mh.current_home_bonus,
    mh.current_away_bonus,
    mh.highlights_video_url,

    coalesce(mh.home_team_id, ml.home_team_id) AS home_team_id,
    coalesce(mh.home_team_club_id, ml.home_club_id) AS home_team_club_id,
    coalesce(mh.home_team_full_name, ml.home_team_full_name) AS home_team_full_name,
    mh.home_team_short_name,
    coalesce(mh.home_team_abbr, ml.home_team_abbr) AS home_team_abbr,
    coalesce(mh.home_team_logo, ml.home_team_logo) AS home_team_logo,
    mh.home_team_logo_alt,
    mh.home_team_secondary_logo,
    mh.home_team_primary_color,
    mh.home_team_text_color,
    mh.home_team_shirt_color,
    mh.home_team_shirt_text_color,

    coalesce(mh.away_team_id, ml.away_team_id) AS away_team_id,
    coalesce(mh.away_team_club_id, ml.away_club_id) AS away_team_club_id,
    coalesce(mh.away_team_full_name, ml.away_team_full_name) AS away_team_full_name,
    mh.away_team_short_name,
    coalesce(mh.away_team_abbr, ml.away_team_abbr) AS away_team_abbr,
    coalesce(mh.away_team_logo, ml.away_team_logo) AS away_team_logo,
    mh.away_team_logo_alt,
    mh.away_team_secondary_logo,
    mh.away_team_primary_color,
    mh.away_team_text_color,
    mh.away_team_shirt_color,
    mh.away_team_shirt_text_color,

    home_bs.head_coach AS home_head_coach,
    home_bs.assistant_coaches AS home_assistant_coaches,
    home_bs.arena AS home_arena,

    away_bs.head_coach AS away_head_coach,
    away_bs.assistant_coaches AS away_assistant_coaches,
    away_bs.arena AS away_arena,

    home_bs.attendance AS attendance,
    home_bs.referees AS referees,

    ml.round_type,
    ml.round_id,
    ml.round_number,
    ml.group_id,
    ml.subphase_id,
    ml.subphase_number,
    ml.match_grouping,

    (coalesce(mh.match_status, ml.match_status) = 'FINALIZED') AS is_played,

    mh.cat_insert_date

FROM ml
LEFT JOIN mh USING (match_id)
LEFT JOIN bs AS home_bs
    ON home_bs.match_id = ml.match_id
   AND home_bs.team_id = coalesce(mh.home_team_id, ml.home_team_id)
   AND home_bs.edition_id = ml.edition_id
LEFT JOIN bs AS away_bs
    ON away_bs.match_id = ml.match_id
   AND away_bs.team_id = coalesce(mh.away_team_id, ml.away_team_id)
   AND away_bs.edition_id = ml.edition_id
