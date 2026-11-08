-- Los dos equipos se alternan el balón: en un cuarto no pueden diferir en más de una posesión.
{{ config(severity='warn') }}

SELECT
    match_id,
    quarter,
    count(*) FILTER (WHERE is_home) AS home_possessions,
    count(*) FILTER (WHERE NOT is_home) AS away_possessions
FROM {{ ref('fact_possessions') }}
GROUP BY match_id, quarter
HAVING abs(count(*) FILTER (WHERE is_home) - count(*) FILTER (WHERE NOT is_home)) > 1
