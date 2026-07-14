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

    COUNT(*) AS field_goals_attempted,

    SUM(CASE WHEN is_made THEN 1 ELSE 0 END) AS field_goals_made,

    ROUND(
        AVG(CASE WHEN is_made THEN 1.0 ELSE 0.0 END),
        4
    ) AS field_goals_pct

FROM {{ ref('fact_shots') }}

GROUP BY
    edition_id,
    zone_id,
    shot_zone_basic,
    shot_zone_area,
    shot_zone_range