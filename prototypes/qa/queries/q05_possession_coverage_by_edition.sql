-- Partidos de equipo con y sin posesiones por edición, y ratings resultantes
SELECT edition_id,
       count(*) AS team_games,
       count(*) FILTER (WHERE has_possessions) AS with_possessions,
       round(100.0 * sum(points) FILTER (WHERE has_possessions)
             / nullif(sum(offensive_possessions), 0), 1) AS league_ortg
FROM main_marts.fact_team_games
GROUP BY edition_id
ORDER BY edition_id;
