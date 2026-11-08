-- Secuencia de posesiones de esos cuartos: equipo, fin, motivo y reloj
WITH bad AS (
    SELECT match_id, quarter
    FROM main_marts.fact_possessions
    GROUP BY match_id, quarter
    HAVING abs(count(*) FILTER (WHERE is_home) - count(*) FILTER (WHERE NOT is_home)) > 1
)
SELECT p.match_id, p.quarter, p.possession_id, p.team_id, p.is_home, p.start_time, p.end_time,
       p.points, p.end_play_type_id, p.end_reason
FROM main_marts.fact_possessions p JOIN bad USING (match_id, quarter)
ORDER BY p.match_id, p.quarter, p.possession_id;
