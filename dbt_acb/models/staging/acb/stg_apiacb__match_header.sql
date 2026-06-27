{{ config(
    materialized='table',
    tags=["acb_statistics"],
    cluster_by=['edition_id', 'match_id']
) }}

WITH source AS (
    SELECT 
        *,        
        CAST(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 1) AS INT) AS extracted_edition_id,
        CAST(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 2) AS INT) AS extracted_match_id
    FROM {{ source('acb_landing', 'match_headers') }}
),

flattened_quarters AS (
    SELECT
        *,
        unnest(quarterScores) AS qs
    FROM source
),

flattened_broadcasters AS (
    SELECT
        *,
        unnest(broadcastChannels) AS bc
    FROM flattened_quarters
)

SELECT
    extracted_edition_id AS edition_id,
    CAST(matchId AS INT) AS match_id,
    CAST(competitionId AS INT) AS competition_id,
    CAST(start AS TIMESTAMP) AS match_start_time,
    CAST(matchStatus AS VARCHAR) AS match_status,
    CAST(isOnHalfTime AS BOOLEAN) AS is_on_half_time,
    CAST(timeLeft AS VARCHAR) AS time_left,
    CAST(currentQuarter AS INT) AS current_quarter,
    CAST(currentHomeScore AS INT) AS current_home_score,
    CAST(currentAwayScore AS INT) AS current_away_score,
    CAST(currentHomeBonus AS INT) AS current_home_bonus,
    CAST(currentAwayBonus AS INT) AS current_away_bonus,
    CAST(highLightsVideoURL AS VARCHAR) AS highlights_video_url,
    CAST(teams.home.id AS INT) AS home_team_id,
    CAST(teams.home.competitionId AS INT) AS home_team_competition_id,
    CAST(teams.home.editionId AS INT) AS home_team_edition_id,
    CAST(teams.home.clubId AS INT) AS home_team_club_id,
    CAST(teams.home.fullName AS VARCHAR) AS home_team_full_name,
    CAST(teams.home.shortName AS VARCHAR) AS home_team_short_name,
    CAST(teams.home.abbreviatedName AS VARCHAR) AS home_team_abbr,
    CAST(teams.home.primaryColorHex AS VARCHAR) AS home_team_primary_color,
    CAST(teams.home.textColorHex AS VARCHAR) AS home_team_text_color,
    CAST(teams.home.logo AS VARCHAR) AS home_team_logo,
    CAST(teams.home.logoAlt AS VARCHAR) AS home_team_logo_alt,
    CAST(teams.home.secondaryLogo AS VARCHAR) AS home_team_secondary_logo,
    CAST(teams.home.shirtColor AS VARCHAR) AS home_team_shirt_color,
    CAST(teams.home.shirtTextColor AS VARCHAR) AS home_team_shirt_text_color,
    CAST(teams.away.id AS INT) AS away_team_id,
    CAST(teams.away.competitionId AS INT) AS away_team_competition_id,
    CAST(teams.away.editionId AS INT) AS away_team_edition_id,
    CAST(teams.away.clubId AS INT) AS away_team_club_id,
    CAST(teams.away.fullName AS VARCHAR) AS away_team_full_name,
    CAST(teams.away.shortName AS VARCHAR) AS away_team_short_name,
    CAST(teams.away.abbreviatedName AS VARCHAR) AS away_team_abbr,
    CAST(teams.away.primaryColorHex AS VARCHAR) AS away_team_primary_color,
    CAST(teams.away.textColorHex AS VARCHAR) AS away_team_text_color,
    CAST(teams.away.logo AS VARCHAR) AS away_team_logo,
    CAST(teams.away.logoAlt AS VARCHAR) AS away_team_logo_alt,
    CAST(teams.away.secondaryLogo AS VARCHAR) AS away_team_secondary_logo,
    CAST(teams.away.shirtColor AS VARCHAR) AS away_team_shirt_color,
    CAST(teams.away.shirtTextColor AS VARCHAR) AS away_team_shirt_text_color,
    CAST(qs.quarter AS INT) AS quarter_number,
    CAST(qs.homeScore AS INT) AS quarter_home_score,
    CAST(qs.awayScore AS INT) AS quarter_away_score,
    CAST(bc.broadcaster AS VARCHAR) AS broadcaster_name,
    CAST(bc.imageLink AS VARCHAR) AS broadcaster_image_link,
    CAST(bc.link AS VARCHAR) AS broadcaster_link,
    CAST(bc.primary AS BOOLEAN) AS is_primary_broadcaster,
    CAST(bc."order" AS INT) AS broadcaster_order,
    CAST(availableContent.overview AS BOOLEAN) AS has_overview_active,
    CAST(availableContent.playbyplay AS BOOLEAN) AS has_playbyplay_active,
    CAST(availableContent.boxscore AS BOOLEAN) AS has_boxscore_active,
    CAST(availableContent.advanced AS BOOLEAN) AS has_advanced_active
FROM flattened_broadcasters