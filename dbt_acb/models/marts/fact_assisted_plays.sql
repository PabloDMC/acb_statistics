{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Una fila por asistencia, con el jugador que asiste y el que anota. En la jugada a jugada de la
-- ACB la asistencia va justo después de la acción que asiste, del mismo equipo y en el mismo
-- segundo:
--   107 Asistencia (2P)  tras 93 (canasta de 2) o 100 (mate)
--   108 Asistencia (3P)  tras 94 (triple)
--   119 Asistencia (TL)  tras 110 (falta recibida): anota el que recibe la falta y los puntos son
--                        los tiros libres que mete en ese mismo segundo
-- Las asistencias que no siguen ese patrón (≈0,5 %, feed desordenado) se descartan.

WITH ev AS (
    SELECT
        edition_id, competition_id, competition_phase, match_id, event_idx,
        quarter, seconds_remaining, play_type_id, player_id, team_id, club_id, is_clutch,
        lag(play_type_id) OVER w AS prev_play_type_id,
        lag(player_id) OVER w AS prev_player_id,
        lag(team_id) OVER w AS prev_team_id,
        lag(quarter) OVER w AS prev_quarter,
        lag(seconds_remaining) OVER w AS prev_seconds_remaining
    FROM {{ ref('fact_play_by_play') }}
    WHERE NOT is_synthetic
    WINDOW w AS (PARTITION BY match_id ORDER BY event_idx)
),

assists AS (
    SELECT
        *,
        CASE play_type_id WHEN 107 THEN '2P' WHEN 108 THEN '3P' ELSE 'FT' END AS play_kind
    FROM ev
    WHERE play_type_id IN (107, 108, 119)
      AND prev_team_id = team_id
      AND prev_quarter = quarter
      AND prev_seconds_remaining = seconds_remaining
      AND prev_player_id IS NOT NULL
      AND prev_player_id <> player_id
      AND (
            (play_type_id = 107 AND prev_play_type_id IN (93, 100))
         OR (play_type_id = 108 AND prev_play_type_id = 94)
         OR (play_type_id = 119 AND prev_play_type_id = 110)
      )
),

-- tiros libres anotados por quien recibió la falta, en el mismo segundo y después de la asistencia
ft AS (
    SELECT
        a.match_id,
        a.event_idx,
        count(*) AS ft_made
    FROM assists a
    JOIN ev f
      ON f.match_id = a.match_id
     AND f.quarter = a.quarter
     AND f.seconds_remaining = a.seconds_remaining
     AND f.player_id = a.prev_player_id
     AND f.play_type_id = 92
     AND f.event_idx > a.event_idx
     AND f.event_idx <= a.event_idx + 12
    WHERE a.play_kind = 'FT'
    GROUP BY a.match_id, a.event_idx
)

SELECT
    concat_ws('_', a.match_id, a.event_idx) AS id,
    a.edition_id,
    a.competition_id,
    a.competition_phase,
    a.match_id,
    a.team_id,
    a.club_id,
    a.player_id AS assist_player_id,
    a.prev_player_id AS scorer_player_id,
    a.play_kind,
    CASE a.play_kind
        WHEN '2P' THEN 2
        WHEN '3P' THEN 3
        ELSE coalesce(ft.ft_made, 0)
    END AS points,
    a.quarter,
    a.seconds_remaining,
    a.is_clutch
FROM assists a
LEFT JOIN ft
    ON ft.match_id = a.match_id
   AND ft.event_idx = a.event_idx
