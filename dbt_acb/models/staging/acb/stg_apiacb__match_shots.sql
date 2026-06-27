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
    FROM {{ source('acb_landing', 'match_shots') }}
),

flattened_shots AS (
    SELECT
        CAST(competitionId AS INT) AS competition_id,
        extracted_edition_id AS edition_id,
        extracted_match_id AS match_id,
        unnest(shotPoints) AS sp 
    FROM source
)

SELECT
    competition_id,
    edition_id,
    match_id,
    CAST(sp.id AS VARCHAR) AS shot_id,
    CAST(sp.posX AS DOUBLE) AS pos_x,
    CAST(sp.posY AS DOUBLE) AS pos_y,
    CAST(sp.playType AS VARCHAR) AS play_type,
    CAST(sp.quarter AS INT) AS quarter,
    CAST(sp.minute AS INT) AS minute,
    CAST(sp.second AS INT) AS second,
    CAST(sp.local AS BOOLEAN) AS is_local_team,
    CAST(sp.scoreHome AS INT) AS score_home,
    CAST(sp.scoreAway AS INT) AS score_away,
    CAST(sp.playerLicenseId AS INT) AS player_license_id
FROM flattened_shots