-- Estructura de la liga regular por temporada: si hay varios grupos o subfases, la clasificación
-- única los mezclaría
SELECT
    m.edition_id, m.competition_id, m.round_type,
    count(*) AS matches,
    count(DISTINCT m.group_id) AS groups,
    count(DISTINCT m.subphase_id) AS subphases,
    count(DISTINCT m.home_team_id) AS teams,
    string_agg(DISTINCT coalesce(m.group_id::VARCHAR, '-'), ',') AS group_ids,
    string_agg(DISTINCT coalesce(m.subphase_id::VARCHAR, '-'), ',') AS subphase_ids
FROM main_marts.dim_matches m
WHERE m.is_played
GROUP BY ALL
ORDER BY m.edition_id, m.competition_id, m.round_type;
