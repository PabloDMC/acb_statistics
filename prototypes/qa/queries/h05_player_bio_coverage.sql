-- Fichas biográficas: % de jugadores con cada dato según la temporada de su primer partido
WITH first_ed AS (
    SELECT player_id, min(edition_id) AS first_edition
    FROM main_intermediate.int_boxscore
    GROUP BY ALL
)
SELECT
    f.first_edition,
    count(*) AS players,
    100.0 * count(p.birth_date) / count(*) AS pct_birth_date,
    100.0 * count(p.height_m) / count(*) AS pct_height,
    100.0 * count(p.nationality) / count(*) AS pct_nationality
FROM first_ed f
LEFT JOIN main_marts.dim_players p USING (player_id)
GROUP BY ALL
ORDER BY f.first_edition;
