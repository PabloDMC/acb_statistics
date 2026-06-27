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
    FROM {{ source('acb_landing', 'play_by_play') }}
),

flattened_plays AS (
    SELECT
        extracted_edition_id AS edition_id,
        extracted_match_id AS match_id,
        unnest(plays) AS p
    FROM source
)

SELECT
    edition_id,
    match_id,
    CAST(p."order" AS INT) AS play_order,
    CAST(p.playerLicenseId AS INT) AS player_license_id,
    CAST(p.licenseType AS VARCHAR) AS license_type,
    CAST(p.playType AS VARCHAR) AS play_type,
    CAST(p.playTag AS VARCHAR) AS play_tag,
    CAST(p.quarter AS INT) AS quarter,
    CAST(p.minute AS INT) AS minute,
    CAST(p.second AS INT) AS second,
    CAST(p.local AS BOOLEAN) AS is_local_action,
    CAST(p.scoreHome AS INT) AS score_home,
    CAST(p.scoreAway AS INT) AS score_away
FROM flattened_plays