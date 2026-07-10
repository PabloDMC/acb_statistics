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

    player_id,

    start_date,
    end_date,

    player_shirt_number,

    player_roles_concat,

    player_is_license_active,

    cat_insert_date

FROM {{ ref('int_players') }}