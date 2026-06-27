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
    FROM {{ source('acb_landing', 'boxscores') }}
),

flattened_periods AS (
    SELECT
        *,
        unnest(teamBoxscores) AS tb
    FROM source
),

flattened_players AS (
    SELECT
        *,
        unnest(tb.statsByPeriods) AS sbp
    FROM flattened_periods
),

final_extraction AS (
    SELECT
        extracted_edition_id AS edition_id,
        extracted_match_id AS match_id,
        CAST(arena AS VARCHAR) AS arena,
        CAST(attendance AS INT) AS attendance,
        CAST(referees AS VARCHAR[]) AS referees,
        CAST(tb.team.id AS INT) AS team_id,
        CAST(tb.headCoach AS VARCHAR) AS head_coach,
        CAST(tb.assistantCoaches AS VARCHAR[]) AS assistant_coaches,
        CAST(sbp.quarter AS INT) AS quarter,
        unnest(sbp.stats.players) AS p
    FROM flattened_players
)

SELECT
    edition_id,
    match_id,
    arena,
    attendance,
    referees,
    team_id,
    head_coach,
    assistant_coaches,
    quarter,
    CAST(p.player.id AS INT) AS player_id,
    CAST(p.player.firstInitialAndLastName AS VARCHAR) AS player_first_initial_and_last_name,
    CAST(p.player.firstName AS VARCHAR) AS player_first_name,
    CAST(p.player.lastName AS VARCHAR) AS player_last_name,
    CAST(p.player.nickname AS VARCHAR) AS player_nickname,
    CAST(p.player.shirtNumber AS INT) AS player_shirt_number,
    CAST(p.player.headshotImageUrl AS VARCHAR) AS player_headshot_image_url,
    CAST(p.player.headshotImageNoBackgroundUrl AS VARCHAR) AS player_headshot_image_no_background_url,
    CAST(p.player.headshotImageAlt AS VARCHAR) AS player_headshot_image_alt,
    CAST(p.player.fullBodyImageUrl AS VARCHAR) AS player_full_body_image_url,
    CAST(p.player.fullBodyImageNoBackgroundUrl AS VARCHAR) AS player_full_body_image_no_background_url,
    CAST(p.player.gameRole AS VARCHAR) AS player_game_role,
    CAST(p.player.isLicenseActive AS BOOLEAN) AS player_is_license_active,
    CAST(p.player.editionId AS INT) AS player_edition_id,
    CAST(p.player.nicknameFirstName AS VARCHAR) AS player_nickname_first_name,
    CAST(p.player.nicknameLastName AS VARCHAR) AS player_nickname_last_name,
    CAST(p.onCourt AS BOOLEAN) AS is_on_court,
    CAST(p.playTime AS VARCHAR) AS play_time,
    CAST(p.isStarted AS BOOLEAN) AS is_starter,
    CAST(p.points AS INT) AS points,
    CAST(p.freeThrowsMade AS INT) AS free_throws_made,
    CAST(p.freeThrowsAttempted AS INT) AS free_throws_attempted,
    CAST(p.twoPointersMade AS INT) AS two_pointers_made,
    CAST(p.twoPointersAttempted AS INT) AS two_pointers_attempted,
    CAST(p.threePointersMade AS INT) AS three_pointers_made,
    CAST(p.threePointersAttempted AS INT) AS three_pointers_attempted,
    CAST(p.dunks AS INT) AS dunks,
    CAST(p.assists AS INT) AS assists,
    CAST(p.offRebounds AS INT) AS off_rebounds,
    CAST(p.defRebounds AS INT) AS def_rebounds,
    CAST(p.totalRebounds AS INT) AS total_rebounds,
    CAST(p.steals AS INT) AS steals,
    CAST(p.turnovers AS INT) AS turnovers,
    CAST(p.blocks AS INT) AS blocks,
    CAST(p.receivedBlocks AS INT) AS received_blocks,
    CAST(p.personalFouls AS INT) AS personal_fouls,
    CAST(p.foulsDrawn AS INT) AS fouls_drawn,
    CAST(p.plusMinus AS INT) AS plus_minus,
    CAST(p.rating AS INT) AS rating
FROM final_extraction