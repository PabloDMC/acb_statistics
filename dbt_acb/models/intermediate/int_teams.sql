{{ config(
    materialized='table',
    schema = "intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'competition_id', 'team_id']
) }}

WITH teams_raw AS (
    SELECT
        edition_id,
        competition_id,
        match_id,
        home_team_id AS team_id,
        home_team_club_id AS club_id,
        home_team_full_name AS full_name,
        home_team_short_name AS short_name,
        home_team_abbr AS abbr,
        home_team_logo AS logo,
        home_team_logo_alt AS logo_alt,
        home_team_secondary_logo AS secondary_logo,
        home_team_primary_color AS primary_color,
        home_team_text_color AS text_color,
        cat_insert_date
    FROM {{ ref('stg_apiacb__match_header') }}

    UNION ALL

    SELECT
        edition_id,
        competition_id,
        match_id,
        away_team_id AS team_id,
        away_team_club_id AS club_id,
        away_team_full_name AS full_name,
        away_team_short_name AS short_name,
        away_team_abbr AS abbr,
        away_team_logo AS logo,
        away_team_logo_alt AS logo_alt,
        away_team_secondary_logo AS secondary_logo,
        away_team_primary_color AS primary_color,
        away_team_text_color AS text_color,
        cat_insert_date
    FROM {{ ref('stg_apiacb__match_header') }}
),

teams_ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY team_id, edition_id, competition_id
            ORDER BY match_id DESC
        ) AS rn
    FROM teams_raw
)

SELECT
    edition_id,
    competition_id,
    team_id,
    club_id,
    full_name,
    short_name,
    abbr,
    logo,
    logo_alt,
    secondary_logo,
    primary_color,
    text_color,
    cat_insert_date
FROM teams_ranked
WHERE rn = 1