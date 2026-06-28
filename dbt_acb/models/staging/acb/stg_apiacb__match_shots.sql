{{ config(
    materialized='table',
    tags=["acb_statistics"],
    cluster_by=['edition_id', 'match_id']
) }}

WITH source AS (
    SELECT 
        *,
        try_cast(regexp_extract(filename, 'ed_(\\d+)_m_(\\d+)', 1) AS INT) AS edition_id,
        try_cast(regexp_extract(filename, 'ed_(\\d+)_m_(\\d+)', 2) AS INT) AS match_id
    FROM {{ source('acb_landing', 'match_shots') }}
),

flattened AS (
    SELECT
        try_cast(competitionId AS INT) AS competition_id,
        edition_id,
        match_id,
        unnest(shotPoints) AS sp
    FROM source
)

SELECT
    competition_id,
    edition_id,
    match_id,
    try_cast(sp.id AS VARCHAR) AS shot_id,
    try_cast(sp.posX AS DOUBLE) AS pos_x,
    try_cast(sp.posY AS DOUBLE) AS pos_y,
    try_cast(sp.playType AS VARCHAR) AS play_type,
    try_cast(sp.quarter AS INT) AS quarter,
    try_cast(sp.minute AS INT) AS minute,
    try_cast(sp.second AS INT) AS second,
    try_cast(sp.local AS BOOLEAN) AS is_local_team,
    try_cast(sp.scoreHome AS INT) AS score_home,
    try_cast(sp.scoreAway AS INT) AS score_away,
    try_cast(sp.playerLicenseId AS INT) AS player_license_id,
    current_timestamp AS cat_insert_date
FROM flattened