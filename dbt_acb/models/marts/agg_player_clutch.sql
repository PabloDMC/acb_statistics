{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Estadísticas en "clutch" (últimos 5 minutos del 4º cuarto y prórrogas con el marcador a 5
-- puntos o menos, ver is_clutch en int_play_by_play), por jugador, equipo y fase. Salen de la
-- jugada a jugada, así que solo cubren partidos con play-by-play.

WITH ev AS (
    SELECT *
    FROM {{ ref('fact_play_by_play') }}
    WHERE is_clutch
      AND player_id IS NOT NULL
      AND NOT is_synthetic
)

SELECT
    edition_id,
    competition_id,
    competition_phase,
    team_id,
    any_value(club_id) AS club_id,
    player_id,
    count(DISTINCT match_id) AS games,
    sum(points) AS points,
    count(*) FILTER (WHERE play_type_id IN (93, 94, 100)) AS field_goals_made,
    count(*) FILTER (WHERE play_type_id IN (93, 94, 100, 97, 98, 533)) AS field_goals_attempted,
    count(*) FILTER (WHERE play_type_id = 94) AS three_pointers_made,
    count(*) FILTER (WHERE play_type_id IN (94, 98)) AS three_pointers_attempted,
    count(*) FILTER (WHERE play_type_id = 92) AS free_throws_made,
    count(*) FILTER (WHERE play_type_id IN (92, 96)) AS free_throws_attempted,
    count(*) FILTER (WHERE play_type_id = 101) AS off_rebounds,
    count(*) FILTER (WHERE play_type_id = 104) AS def_rebounds,
    count(*) FILTER (WHERE play_type_id IN (101, 104)) AS total_rebounds,
    count(*) FILTER (WHERE play_type_id IN (107, 108, 119)) AS assists,
    count(*) FILTER (WHERE play_type_id = 103) AS steals,
    count(*) FILTER (WHERE play_type_id = 102) AS blocks,
    count(*) FILTER (WHERE play_type_id = 106) AS turnovers
FROM ev
GROUP BY edition_id, competition_id, competition_phase, team_id, player_id
