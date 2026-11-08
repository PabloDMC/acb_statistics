{{ config(
    materialized='table',
    schema='intermediate',
    tags=['acb_analytics'],
    cluster_by=['match_id']
) }}

-- Una fila por tramo: periodo de un cuarto en el que los 10 jugadores en pista no cambian.
-- Puntos = los anotados durante el tramo; posesiones = las que TERMINAN en el tramo. Así la
-- suma de los tramos de un partido es exactamente el total del equipo.

WITH ev AS (
    SELECT
        p.match_id,
        p.event_idx,
        p.quarter,
        p.seconds_remaining,
        p.team_id,
        p.home_team_id,
        p.away_team_id,
        p.points,
        e.stint_seq,
        e.home_lineup,
        e.away_lineup
    FROM {{ ref('int_play_by_play') }} p
    JOIN {{ ref('int_pbp_enriched') }} e
        USING (match_id, event_idx)
),

stints AS (
    SELECT
        match_id,
        quarter,
        stint_seq,
        any_value(home_team_id) AS home_team_id,
        any_value(away_team_id) AS away_team_id,
        min(event_idx) AS start_event_idx,
        max(event_idx) AS end_event_idx,
        arg_min(seconds_remaining, event_idx) AS start_time,
        arg_max(home_lineup, event_idx) AS home_lineup,
        arg_max(away_lineup, event_idx) AS away_lineup,
        sum(CASE WHEN team_id = home_team_id THEN points ELSE 0 END) AS home_points,
        sum(CASE WHEN team_id = away_team_id THEN points ELSE 0 END) AS away_points
    FROM ev
    GROUP BY match_id, quarter, stint_seq
),

-- Reloj de inicio de cada tramo, saneado. El feed a veces trae relojes fuera de orden: en los
-- partidos 103148 y 103422 el primer evento del 2º cuarto marca 1:00 (antes del 10:00) y el
-- cuarto sumaba 60 s. Dos reglas:
--   1. el primer tramo del cuarto empieza con el cuarto (600 s, 300 en la prórroga);
--   2. el reloj no puede crecer: cada inicio se limita al del tramo anterior.
-- Se hace a nivel de tramo y no de evento porque el feed también añade correcciones tardías al
-- final de cuartos ya acabados, con su reloj real, y un máximo por evento las arrastraría hacia atrás.
anchored AS (
    SELECT
        * EXCLUDE (start_time),
        CASE
            WHEN stint_seq = min(stint_seq) OVER (PARTITION BY match_id, quarter)
                THEN CASE WHEN quarter <= 4 THEN 600 ELSE 300 END
            ELSE start_time
        END AS raw_start_time
    FROM stints
),

clocked AS (
    SELECT
        * EXCLUDE (raw_start_time),
        min(raw_start_time) OVER (
            PARTITION BY match_id, quarter ORDER BY stint_seq
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS start_time
    FROM anchored
),

timed AS (
    SELECT
        *,
        -- El tramo acaba donde empieza el siguiente del mismo cuarto (o en 0). Con esta regla los
        -- segundos por jugador coinciden con los minutos del boxscore.
        coalesce(
            lead(start_time) OVER (PARTITION BY match_id, quarter ORDER BY stint_seq),
            0
        ) AS end_time
    FROM clocked
),

poss AS (
    SELECT
        match_id,
        stint_seq,
        count(*) FILTER (WHERE team_id = home_team_id) AS home_possessions,
        count(*) FILTER (WHERE team_id = away_team_id) AS away_possessions
    FROM {{ ref('int_possessions') }}
    WHERE is_counted
    GROUP BY match_id, stint_seq
),

final AS (
    SELECT
        t.match_id,
        t.quarter,
        t.stint_seq,
        t.home_team_id,
        t.away_team_id,
        t.start_event_idx,
        t.end_event_idx,
        t.start_time,
        t.end_time,
        t.start_time - t.end_time AS seconds,
        t.home_lineup,
        t.away_lineup,
        CASE WHEN t.home_lineup = '' THEN CAST([] AS INT[]) ELSE CAST(string_split(t.home_lineup, '-') AS INT[]) END AS home_player_ids,
        CASE WHEN t.away_lineup = '' THEN CAST([] AS INT[]) ELSE CAST(string_split(t.away_lineup, '-') AS INT[]) END AS away_player_ids,
        t.home_points,
        t.away_points,
        coalesce(p.home_possessions, 0) AS home_possessions,
        coalesce(p.away_possessions, 0) AS away_possessions
    FROM timed t
    LEFT JOIN poss p
        ON p.match_id = t.match_id
       AND p.stint_seq = t.stint_seq
)

SELECT
    concat_ws('_', match_id, stint_seq) AS id,
    *
FROM final
-- Entre el bloque de cambios de un equipo y el del otro queda un tramo vacío de 0 segundos.
WHERE NOT (
    seconds = 0
    AND home_points + away_points + home_possessions + away_possessions = 0
)
