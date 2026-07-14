{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

SELECT

    id AS roster_id,
    edition_id,
    competition_id,
    team_id,
    club_id,
    player_id,
    player_first_name,
    player_last_name,
    player_first_initial_and_last_name,
    player_nickname,
    player_nickname_first_name,
    player_nickname_last_name,
    player_headshot_image_url,
    player_headshot_image_no_background_url,
    player_shirt_number,
    player_roles_concat,
    player_is_license_active,
    start_date,
    end_date,
    cat_insert_date

FROM {{ ref('int_players') }}