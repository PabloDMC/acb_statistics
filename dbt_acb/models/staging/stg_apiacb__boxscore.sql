{{ config(
    materialized='table',
    schema = "staging",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'match_id']
) }}

WITH source AS (
    SELECT 
        *,
        try_cast(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 1) AS INT) AS edition_id,
        try_cast(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 2) AS INT) AS match_id
    FROM {{ source('acb_landing', 'boxscores') }}
),

flattened_team_boxscores AS (
    SELECT
        *,
        unnest(teamBoxscores) AS tb
    FROM source
),

flattened_periods AS (
    SELECT
        *,
        unnest(tb.statsByPeriods) AS sbp
    FROM flattened_team_boxscores
),

flattened_players AS (
    SELECT
        *,
        unnest(sbp.stats.players) AS p
    FROM flattened_periods
),

normalized_player_json AS (
    SELECT
        *,
        try_cast(p.player AS JSON) AS player_json
    FROM flattened_players
)

SELECT
    edition_id,
    match_id,
    try_cast(arena AS VARCHAR) AS arena,
    try_cast(attendance AS INT) AS attendance,
    try_cast(referees AS VARCHAR[]) AS referees,
    try_cast(tb.team.id AS INT) AS team_id,
    try_cast(tb.team.clubId AS INT) AS club_id,
    try_cast(tb.headCoach AS VARCHAR) AS head_coach,
    try_cast(tb.assistantCoaches AS VARCHAR[]) AS assistant_coaches,
    try_cast(sbp.quarter AS INT) AS quarter,
    try_cast(player_json ->> 'id' AS INT) AS player_id,
    try_cast(player_json ->> 'firstInitialAndLastName' AS VARCHAR) AS player_first_initial_and_last_name,
    try_cast(player_json ->> 'firstName' AS VARCHAR) AS player_first_name,
    try_cast(player_json ->> 'lastName' AS VARCHAR) AS player_last_name,
    try_cast(player_json ->> 'nickname' AS VARCHAR) AS player_nickname,
    try_cast(player_json ->> 'shirtNumber' AS VARCHAR) AS player_shirt_number,
    try_cast(player_json ->> 'headshotImageUrl' AS VARCHAR) AS player_headshot_image_url,
    try_cast(player_json ->> 'headshotImageNoBackgroundUrl' AS VARCHAR) AS player_headshot_image_no_background_url,
    try_cast(player_json ->> 'headshotImageAlt' AS VARCHAR) AS player_headshot_image_alt,
    try_cast(player_json ->> 'fullBodyImageUrl' AS VARCHAR) AS player_full_body_image_url,
    try_cast(player_json ->> 'fullBodyImageNoBackgroundUrl' AS VARCHAR) AS player_full_body_image_no_background_url,
    try_cast(player_json ->> 'gameRole' AS VARCHAR) AS player_game_role,
    try_cast(player_json ->> 'isLicenseActive' AS BOOLEAN) AS player_is_license_active,
    try_cast(player_json ->> 'editionId' AS INT) AS player_edition_id,
    try_cast(player_json ->> 'nicknameFirstName' AS VARCHAR) AS player_nickname_first_name,
    try_cast(player_json ->> 'nicknameLastName' AS VARCHAR) AS player_nickname_last_name,
    try_cast(p.onCourt AS BOOLEAN) AS is_on_court,
    try_cast(p.playTime AS VARCHAR) AS play_time,
    try_cast(p.isStarted AS BOOLEAN) AS is_starter,
    try_cast(p.points AS INT) AS points,
    try_cast(p.freeThrowsMade AS INT) AS free_throws_made,
    try_cast(p.freeThrowsAttempted AS INT) AS free_throws_attempted,
    try_cast(p.twoPointersMade AS INT) AS two_pointers_made,
    try_cast(p.twoPointersAttempted AS INT) AS two_pointers_attempted,
    try_cast(p.threePointersMade AS INT) AS three_pointers_made,
    try_cast(p.threePointersAttempted AS INT) AS three_pointers_attempted,
    try_cast(p.dunks AS INT) AS dunks,
    try_cast(p.assists AS INT) AS assists,
    try_cast(p.offRebounds AS INT) AS off_rebounds,
    try_cast(p.defRebounds AS INT) AS def_rebounds,
    try_cast(p.totalRebounds AS INT) AS total_rebounds,
    try_cast(p.steals AS INT) AS steals,
    try_cast(p.turnovers AS INT) AS turnovers,
    try_cast(p.blocks AS INT) AS blocks,
    try_cast(p.receivedBlocks AS INT) AS received_blocks,
    try_cast(p.personalFouls AS INT) AS personal_fouls,
    try_cast(p.foulsDrawn AS INT) AS fouls_drawn,
    try_cast(p.plusMinus AS INT) AS plus_minus,
    try_cast(p.rating AS INT) AS rating,
    current_timestamp AS cat_insert_date
FROM normalized_player_json