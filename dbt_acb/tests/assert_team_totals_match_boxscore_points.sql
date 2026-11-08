-- Los puntos del bloque `total` del boxscore deben coincidir con el marcador de la cabecera.
{{ config(severity='warn') }}

SELECT
    g.match_id,
    g.team_id,
    g.points AS header_points,
    b.points AS boxscore_points
FROM {{ ref('fact_team_games') }} g
JOIN {{ ref('int_team_boxscore') }} b
    ON b.match_id = g.match_id
   AND b.team_id = g.team_id
WHERE g.points <> b.points
