{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

SELECT DISTINCT

    competition_id,

    CASE competition_id
        WHEN 1 THEN 'Liga Endesa'
        WHEN 2 THEN 'Copa del Rey'
        WHEN 3 THEN 'Supercopa'
    END AS competition_name

FROM {{ ref('stg_apiacb__competition') }}

ORDER BY competition_id