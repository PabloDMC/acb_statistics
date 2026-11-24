-- Cobertura por temporada y competición: partidos jugados y cuántos tienen cada tipo de dato
SELECT
    m.edition_id, e.season_name, m.competition_id,
    count(*) FILTER (WHERE m.is_played) AS played,
    count(*) FILTER (WHERE m.has_boxscore) AS with_boxscore,
    count(*) FILTER (WHERE m.has_play_by_play) AS with_pbp,
    count(*) FILTER (WHERE m.has_shots) AS with_shots,
    count(*) FILTER (WHERE m.is_played AND (m.home_score IS NULL OR m.away_score IS NULL)) AS played_without_score,
    string_agg(DISTINCT m.round_type, ',') AS phases
FROM main_marts.dim_matches m
LEFT JOIN main_marts.dim_editions e ON e.edition_id = m.edition_id
GROUP BY ALL
ORDER BY m.edition_id, m.competition_id;
