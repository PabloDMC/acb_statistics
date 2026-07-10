{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

SELECT DISTINCT

    edition_id,

    season_start_year,
    season_end_year,

    concat(
        season_start_year,
        '-',
        season_end_year
    ) AS season_name

FROM {{ ref('stg_apiacb__competition') }}

ORDER BY edition_id