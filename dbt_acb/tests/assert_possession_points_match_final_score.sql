-- Los puntos repartidos en posesiones (y, por tanto, en tramos y quintetos) tienen que sumar el
-- marcador final de cada equipo. Si falla en un partido, a su play-by-play le faltan canastas.
{{ config(severity='warn') }}

WITH from_possessions AS (
    SELECT match_id, team_id, sum(points) AS points
    FROM (
        SELECT match_id, team_id, points FROM {{ ref('int_possessions') }}
        UNION ALL
        SELECT match_id, opponent_team_id, opponent_points FROM {{ ref('int_possessions') }}
    )
    GROUP BY match_id, team_id
)

SELECT
    g.match_id,
    g.team_id,
    g.points AS final_score,
    coalesce(p.points, 0) AS points_in_possessions
FROM {{ ref('fact_team_games') }} g
LEFT JOIN from_possessions p
    ON p.match_id = g.match_id
   AND p.team_id = g.team_id
WHERE g.offensive_possessions IS NOT NULL
  AND g.points <> coalesce(p.points, 0)
