{{ config(
    materialized='table',
    tags=["acb_statistics"],
    cluster_by=['edition_id', 'match_id']
) }}

WITH src AS (
    SELECT 
        *,
        try_cast(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 1) AS INT) AS edition_id,
        try_cast(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 2) AS INT) AS match_id
    FROM {{ source('acb_landing', 'match_headers') }}
),

quarters AS (
    SELECT *, unnest(quarterScores) AS qs
    FROM src
),

broadcasters AS (
    SELECT *, unnest(broadcastChannels) AS bc
    FROM quarters
)

SELECT
    edition_id,
    match_id,

    try_cast(competitionId AS INT) AS competition_id,
    try_cast(start AS TIMESTAMP) AS match_start_time,
    try_cast(matchStatus AS VARCHAR) AS match_status,
    try_cast(isOnHalfTime AS BOOLEAN) AS is_on_half_time,
    try_cast(timeLeft AS VARCHAR) AS time_left,
    try_cast(currentQuarter AS INT) AS current_quarter,
    try_cast(currentHomeScore AS INT) AS current_home_score,
    try_cast(currentAwayScore AS INT) AS current_away_score,
    try_cast(currentHomeBonus AS INT) AS current_home_bonus,
    try_cast(currentAwayBonus AS INT) AS current_away_bonus,
    try_cast(highLightsVideoURL AS VARCHAR) AS highlights_video_url,
    try_cast(teams.home ->> 'id' AS INT) AS home_team_id,
    try_cast(teams.home ->> 'competitionId' AS INT) AS home_team_competition_id,
    try_cast(teams.home ->> 'editionId' AS INT) AS home_team_edition_id,
    try_cast(teams.home ->> 'clubId' AS INT) AS home_team_club_id,
    try_cast(teams.home ->> 'fullName' AS VARCHAR) AS home_team_full_name,
    try_cast(teams.home ->> 'shortName' AS VARCHAR) AS home_team_short_name,
    try_cast(teams.home ->> 'abbreviatedName' AS VARCHAR) AS home_team_abbr,
    try_cast(teams.home ->> 'primaryColorHex' AS VARCHAR) AS home_team_primary_color,
    try_cast(teams.home ->> 'textColorHex' AS VARCHAR) AS home_team_text_color,
    try_cast(teams.home ->> 'logo' AS VARCHAR) AS home_team_logo,
    try_cast(teams.home ->> 'logoAlt' AS VARCHAR) AS home_team_logo_alt,
    try_cast(teams.home ->> 'secondaryLogo' AS VARCHAR) AS home_team_secondary_logo,
    try_cast(teams.home ->> 'shirtColor' AS VARCHAR) AS home_team_shirt_color,
    try_cast(teams.home ->> 'shirtTextColor' AS VARCHAR) AS home_team_shirt_text_color,
    try_cast(teams.away ->> 'id' AS INT) AS away_team_id,
    try_cast(teams.away ->> 'competitionId' AS INT) AS away_team_competition_id,
    try_cast(teams.away ->> 'editionId' AS INT) AS away_team_edition_id,
    try_cast(teams.away ->> 'clubId' AS INT) AS away_team_club_id,
    try_cast(teams.away ->> 'fullName' AS VARCHAR) AS away_team_full_name,
    try_cast(teams.away ->> 'shortName' AS VARCHAR) AS away_team_short_name,
    try_cast(teams.away ->> 'abbreviatedName' AS VARCHAR) AS away_team_abbr,
    try_cast(teams.away ->> 'primaryColorHex' AS VARCHAR) AS away_team_primary_color,
    try_cast(teams.away ->> 'textColorHex' AS VARCHAR) AS away_team_text_color,
    try_cast(teams.away ->> 'logo' AS VARCHAR) AS away_team_logo,
    try_cast(teams.away ->> 'logoAlt' AS VARCHAR) AS away_team_logo_alt,
    try_cast(teams.away ->> 'secondaryLogo' AS VARCHAR) AS away_team_secondary_logo,
    try_cast(teams.away ->> 'shirtColor' AS VARCHAR) AS away_team_shirt_color,
    try_cast(teams.away ->> 'shirtTextColor' AS VARCHAR) AS away_team_shirt_text_color,
    try_cast(qs.quarter AS INT) AS quarter_number,
    try_cast(qs.homeScore AS INT) AS quarter_home_score,
    try_cast(qs.awayScore AS INT) AS quarter_away_score,
    try_cast(bc.broadcaster AS VARCHAR) AS broadcaster_name,
    try_cast(bc.imageLink AS VARCHAR) AS broadcaster_image_link,
    try_cast(bc.link AS VARCHAR) AS broadcaster_link,
    try_cast(bc.primary AS BOOLEAN) AS is_primary_broadcaster,
    try_cast(bc."order" AS INT) AS broadcaster_order,
    try_cast(availableContent ->> 'overview' AS BOOLEAN) AS has_overview_active,
    try_cast(availableContent ->> 'playbyplay' AS BOOLEAN) AS has_playbyplay_active,
    try_cast(availableContent ->> 'boxscore' AS BOOLEAN) AS has_boxscore_active,
    try_cast(availableContent ->> 'advanced' AS BOOLEAN) AS has_advanced_active,
    current_timestamp AS cat_insert_date,
    current_timestamp AS cat_insert_date
FROM broadcasters