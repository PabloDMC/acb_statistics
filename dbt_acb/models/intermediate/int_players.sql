{{ config(
    materialized='table',
    schema = "intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'player_id', 'club_id']
) }}

WITH bs AS (
    SELECT
        b.*,
        mh.match_start_time
    FROM {{ ref('stg_apiacb__boxscore') }} b
    LEFT JOIN {{ ref('stg_apiacb__match_header') }} mh
        ON b.match_id = mh.match_id
),

players_clean AS (
    SELECT *
    FROM bs
    WHERE quarter = 0
),

club_ranges AS (
    SELECT
        player_id,
        edition_id,
        club_id,
        MIN(match_start_time) AS start_date,
        MAX(match_start_time) AS end_date
    FROM players_clean
    GROUP BY player_id, edition_id, club_id
),

roles_concat AS (
    SELECT
        player_id,
        edition_id,
        club_id,
        STRING_AGG(DISTINCT player_game_role, ', ') AS roles_concat
    FROM players_clean
    GROUP BY player_id, edition_id, club_id
),

identity_ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY player_id, edition_id, club_id
            ORDER BY match_start_time DESC
        ) AS rn_id
    FROM players_clean
)

SELECT
    concat_ws('_', r.player_id, r.edition_id, r.club_id) AS id,

    r.player_id,
    r.edition_id,
    r.club_id,

    r.start_date,
    r.end_date,

    i.player_first_name,
    i.player_last_name,
    i.player_nickname,
    i.player_first_initial_and_last_name,
    i.player_nickname_first_name,
    i.player_nickname_last_name,

    i.player_shirt_number,
    i.player_headshot_image_url,
    i.player_headshot_image_no_background_url,
    i.player_headshot_image_alt,
    i.player_full_body_image_url,
    i.player_full_body_image_no_background_url,

    i.player_is_license_active,

    rc.roles_concat AS player_roles_concat,

    i.cat_insert_date

FROM club_ranges r
LEFT JOIN identity_ranked i
    ON r.player_id = i.player_id
   AND r.edition_id = i.edition_id
   AND r.club_id = i.club_id
   AND i.rn_id = 1
LEFT JOIN roles_concat rc
    ON r.player_id = rc.player_id
   AND r.edition_id = rc.edition_id
   AND r.club_id = rc.club_id