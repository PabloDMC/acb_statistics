{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH clubs_ranked AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY club_id
            ORDER BY edition_id DESC, competition_id ASC
        ) AS rn
    FROM {{ ref('int_teams') }}

)

SELECT

    club_id,

    full_name,
    short_name,
    abbr,

    logo,
    secondary_logo,

    primary_color,
    text_color,

    cat_insert_date

FROM clubs_ranked

WHERE rn = 1