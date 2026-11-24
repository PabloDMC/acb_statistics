-- Partidos en los que los puntos del bloque `total` del boxscore no cuadran con el marcador:
-- resumen por temporada (diferencia y si la suma de jugadores sí cuadra con alguno de los dos)
WITH players AS (
    SELECT match_id, team_id, sum(points) AS player_points
    FROM main_intermediate.int_boxscore
    GROUP BY ALL
),
x AS (
    SELECT g.edition_id, g.competition_id, g.match_id, g.team_id,
           g.points AS header_points, b.points AS box_total_points, p.player_points
    FROM main_marts.fact_team_games g
    JOIN main_intermediate.int_team_boxscore b USING (match_id, team_id)
    LEFT JOIN players p USING (match_id, team_id)
    WHERE g.points <> b.points
)
SELECT edition_id, competition_id, count(*) AS team_games,
       count(*) FILTER (WHERE player_points = header_points) AS players_match_header,
       count(*) FILTER (WHERE player_points = box_total_points) AS players_match_box_total,
       avg(abs(header_points - box_total_points)) AS avg_abs_diff,
       max(abs(header_points - box_total_points)) AS max_abs_diff,
       any_value(match_id) AS example_match
FROM x
GROUP BY ALL
ORDER BY edition_id, competition_id;
