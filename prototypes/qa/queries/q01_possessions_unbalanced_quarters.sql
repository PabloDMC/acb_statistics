-- Los 2 avisos de assert_possessions_balanced_by_quarter, con el detalle de cada cuarto
WITH q AS (
    SELECT match_id, quarter,
           count(*) FILTER (WHERE is_home) AS home_poss,
           count(*) FILTER (WHERE NOT is_home) AS away_poss
    FROM main_marts.fact_possessions
    GROUP BY match_id, quarter
    HAVING abs(home_poss - away_poss) > 1
)
SELECT q.*, m.edition_id, m.home_team_id, m.away_team_id
FROM q LEFT JOIN main_marts.dim_matches m USING (match_id)
ORDER BY match_id, quarter;
