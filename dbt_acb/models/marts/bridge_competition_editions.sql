{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

SELECT DISTINCT

    competition_id,
    edition_id

FROM {{ ref('stg_apiacb__competition') }}

ORDER BY
    competition_id,
    edition_id