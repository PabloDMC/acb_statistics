{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

SELECT

    team_id,
    club_id,

    edition_id,
    competition_id,

    full_name,
    short_name,
    abbr,

    logo,
    secondary_logo,

    primary_color,
    text_color,

    cat_insert_date

FROM {{ ref('int_teams') }}