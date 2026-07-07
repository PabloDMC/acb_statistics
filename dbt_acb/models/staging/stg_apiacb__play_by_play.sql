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
    FROM {{ source('acb_landing', 'play_by_play') }}
),

flattened AS (
    SELECT
        edition_id,
        match_id,
        unnest(plays) AS p
    FROM source
)

SELECT
    edition_id,
    match_id,
    try_cast(p."order" AS INT) AS play_order,
    try_cast(p.playerLicenseId AS INT) AS player_license_id,
    try_cast(p.licenseType AS VARCHAR) AS license_type,
    try_cast(p.playType AS INT) AS play_type,
    try_cast(p.playTag AS VARCHAR) AS play_tag,
    try_cast(p.quarter AS INT) AS quarter,
    try_cast(p.minute AS INT) AS minute,
    try_cast(p.second AS INT) AS second,
    try_cast(p.local AS BOOLEAN) AS is_local_action,
    try_cast(p.scoreHome AS INT) AS score_home,
    try_cast(p.scoreAway AS INT) AS score_away,
    current_timestamp AS cat_insert_date
FROM flattened