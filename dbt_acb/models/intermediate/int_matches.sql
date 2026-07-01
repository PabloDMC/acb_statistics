{{ config(
    materialized='table',
    schema = "intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'competition_id', 'match_id']
) }}

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
    mh.competition_id,
    ml.week_id,

    mh.match_start_time,
    mh.match_status,
    mh.is_on_half_time,
    mh.time_left,
    mh.current_quarter,
    mh.current_home_score,
    mh.current_away_score,
    mh.current_home_bonus,
    mh.current_away_bonus,
    mh.highlights_video_url,

    mh.home_team_id,
    mh.home_team_club_id,
    mh.home_team_full_name,
    mh.home_team_short_name,
    mh.home_team_abbr,
    mh.home_team_logo,
    mh.home_team_logo_alt,
    mh.home_team_secondary_logo,
    mh.home_team_primary_color,
    mh.home_team_text_color,
    mh.home_team_shirt_color,
    mh.home_team_shirt_text_color,

    mh.away_team_id,
    mh.away_team_club_id,
    mh.away_team_full_name,
    mh.away_team_short_name,
    mh.away_team_abbr,
    mh.away_team_logo,
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

    mh.cat_insert_date

FROM ml
LEFT JOIN mh USING (match_id)
LEFT JOIN bs AS home_bs
    ON home_bs.match_id = ml.match_id
   AND home_bs.team_id = mh.home_team_id
   AND home_bs.edition_id = ml.edition_id
LEFT JOIN bs AS away_bs
    ON away_bs.match_id = ml.match_id
   AND away_bs.team_id = mh.away_team_id
   AND away_bs.edition_id = ml.edition_id
