{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH ranked AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY player_id
            ORDER BY
                end_date DESC NULLS LAST,
                edition_id DESC
        ) AS rn
    FROM {{ ref('int_players') }}

)

SELECT

    player_id,

    player_first_name,
    player_last_name,

    player_nickname,

    player_first_initial_and_last_name,

    player_nickname_first_name,
    player_nickname_last_name,

    player_headshot_image_url,
    player_headshot_image_no_background_url

FROM ranked

WHERE rn = 1