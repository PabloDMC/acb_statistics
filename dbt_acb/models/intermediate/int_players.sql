{{ config(
    materialized='table',
    schema="intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'competition_id', 'team_id', 'player_id']
) }}

WITH bs AS (

    SELECT
        b.*,
        mh.match_start_time,
        mh.competition_id
    FROM {{ ref('stg_apiacb__boxscore') }} b
    LEFT JOIN {{ ref('stg_apiacb__match_header') }} mh
        ON b.match_id = mh.match_id

),

players_clean AS (

    SELECT *
    FROM bs
    WHERE quarter = 0

),

roster_ranges AS (

    SELECT

        player_id,
        edition_id,
        competition_id,
        team_id,
        club_id,

        MIN(match_start_time) AS start_date,
        MAX(match_start_time) AS end_date

    FROM players_clean

    GROUP BY

        player_id,
        edition_id,
        competition_id,
        team_id,
        club_id

),

roles_concat AS (

    SELECT

        player_id,
        edition_id,
        competition_id,
        team_id,
        club_id,

        STRING_AGG(
            DISTINCT player_game_role,
            ', '
        ) AS roles_concat

    FROM players_clean

    GROUP BY

        player_id,
        edition_id,
        competition_id,
        team_id,
        club_id

),

identity_ranked AS (

    SELECT *,

        ROW_NUMBER() OVER (

            PARTITION BY

                player_id,
                edition_id,
                competition_id,
                team_id

            ORDER BY match_start_time DESC

        ) AS rn

    FROM players_clean

)

SELECT

    concat_ws(
        '_',
        i.player_id,
        i.team_id
    ) AS id,

    i.player_id,

    i.edition_id,
    i.competition_id,

    i.team_id,
    i.club_id,

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

FROM identity_ranked i

LEFT JOIN roster_ranges r

ON i.player_id = r.player_id
AND i.team_id = r.team_id

LEFT JOIN roles_concat rc

ON i.player_id = rc.player_id
AND i.team_id = rc.team_id

WHERE rn = 1