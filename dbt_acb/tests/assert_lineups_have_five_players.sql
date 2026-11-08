-- Tramos con tiempo de juego en los que algún equipo no tiene 5 jugadores: al play-by-play de ese
-- partido le faltan cambios. Sus minutos y su on/off no son fiables.
{{ config(severity='warn') }}

SELECT
    match_id,
    team_id,
    stint_id,
    quarter,
    duration_seconds,
    len(player_ids) AS players_on_court
FROM {{ ref('fact_lineups') }}
WHERE duration_seconds > 0
  AND len(player_ids) <> 5
