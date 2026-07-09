{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

SELECT

    edition_id,

    zone_id,
    shot_zone_basic,
    shot_zone_area,
    shot_zone_range,

    COUNT(*) AS fga,

    SUM(CASE WHEN is_made THEN 1 ELSE 0 END) AS fgm,

    ROUND(
        AVG(CASE WHEN is_made THEN 1.0 ELSE 0.0 END),
        4
    ) AS fg_pct

FROM {{ ref('fact_shots') }}

GROUP BY
    edition_id,
    zone_id,
    shot_zone_basic,
    shot_zone_area,
    shot_zone_range