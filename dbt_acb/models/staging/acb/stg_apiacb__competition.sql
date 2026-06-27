{{ config(
    materialized='table',
    tags=["acb_statistics"],
    cluster_by=['competition_id', 'edition_id']
) }}

WITH source AS (
    SELECT 
        *,
        CAST(regexp_extract(filename, 'comp_(\d+)', 1) AS INT) AS file_competition_id
    FROM {{ source('acb_landing', 'competitions') }}
),

flattened_competitions AS (
    SELECT
        file_competition_id AS competition_id,
        CAST(currentCompetitionId AS INT) AS current_competition_id,
        CAST(currentEditionId AS INT) AS current_edition_id,
        CAST(currentWeekId AS INT) AS current_week_id,
        CAST(currentRoundId AS INT) AS current_round_id,
        CAST(currentMatchGrouping AS VARCHAR) AS current_match_grouping,
        unnest(competitions) AS c
    FROM source
),

flattened_editions AS (
    SELECT
        competition_id,
        current_competition_id,
        current_edition_id,
        current_week_id,
        current_round_id,
        current_match_grouping,
        unnest(c.editions) AS ed
    FROM flattened_competitions
),

flattened_weeks AS (
    SELECT
        competition_id,
        current_competition_id,
        current_edition_id,
        current_week_id,
        current_round_id,
        current_match_grouping,
        CAST(ed.id AS INT) AS edition_id,
        CAST(ed.seasonStartYear AS INT) AS season_start_year,
        CAST(ed.seasonEndYear AS INT) AS season_end_year,
        unnest(ed.weeks) AS w
    FROM flattened_editions
)

SELECT
    competition_id,
    edition_id,
    season_start_year,
    season_end_year,
    CAST(w.id AS INT) AS week_id,
    CAST(w.description AS VARCHAR) AS week_description,
    CAST(w.startDate AS DATE) AS week_start_date,
    current_competition_id,
    current_edition_id,
    current_week_id,
    current_round_id,
    current_match_grouping
FROM flattened_weeks