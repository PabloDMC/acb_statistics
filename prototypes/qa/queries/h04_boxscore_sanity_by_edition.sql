-- Qué estadísticas trae de verdad el boxscore de cada temporada (Liga): medias por equipo y
-- partido y % de partidos con cada estadística a 0 (señal de que no se registraba)
SELECT
    edition_id,
    count(*) AS team_games,
    avg(points) AS pts,
    avg(seconds) / 60 AS player_minutes,
    avg(three_pointers_attempted) AS fg3a,
    avg(off_rebounds) AS orb,
    avg(def_rebounds) AS drb,
    avg(total_rebounds) AS trb,
    avg(assists) AS ast,
    avg(steals) AS stl,
    avg(turnovers) AS tov,
    avg(blocks) AS blk,
    avg(personal_fouls) AS pf,
    avg(fouls_drawn) AS fd,
    avg(rating) AS val,
    100.0 * count(*) FILTER (WHERE coalesce(off_rebounds, 0) = 0) / count(*) AS pct_no_orb,
    100.0 * count(*) FILTER (WHERE coalesce(assists, 0) = 0) / count(*) AS pct_no_ast,
    100.0 * count(*) FILTER (WHERE coalesce(steals, 0) = 0) / count(*) AS pct_no_stl,
    100.0 * count(*) FILTER (WHERE coalesce(turnovers, 0) = 0) / count(*) AS pct_no_tov,
    100.0 * count(*) FILTER (WHERE coalesce(blocks, 0) = 0) / count(*) AS pct_no_blk,
    100.0 * count(*) FILTER (WHERE seconds IS NULL OR seconds = 0) / count(*) AS pct_no_minutes,
    100.0 * count(*) FILTER (WHERE free_throws_attempted IS NULL) / count(*) AS pct_no_box
FROM main_marts.fact_team_games
WHERE competition_id = 1
GROUP BY ALL
ORDER BY edition_id;
