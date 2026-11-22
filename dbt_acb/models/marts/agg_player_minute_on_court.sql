{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Mapa de rotaciones: una fila por jugador, equipo, fase y MINUTO de partido (0 a 39, sin
-- prórrogas). Para cada minuto, en cuántos partidos del equipo estuvo en pista y cuántos
-- segundos acumuló. Sale de los tramos (int_stints): los 10 jugadores en pista en cada momento.

WITH stints AS (
    SELECT
        s.match_id,
        s.quarter,
        -- segundos transcurridos de partido al empezar y acabar el tramo (el reloj cuenta atrás)
        (s.quarter - 1) * 600 + (600 - s.start_time) AS elapsed_start,
        (s.quarter - 1) * 600 + (600 - s.end_time) AS elapsed_end,
        s.home_team_id,
        s.away_team_id,
        s.home_player_ids,
        s.away_player_ids
    FROM {{ ref('int_stints') }} s
    WHERE s.quarter <= 4
      AND s.end_time < s.start_time
),

players AS (
    SELECT match_id, elapsed_start, elapsed_end, home_team_id AS team_id, UNNEST(home_player_ids) AS player_id
    FROM stints
    UNION ALL
    SELECT match_id, elapsed_start, elapsed_end, away_team_id AS team_id, UNNEST(away_player_ids) AS player_id
    FROM stints
),

-- cada tramo repartido entre los minutos que toca
by_minute AS (
    SELECT
        match_id,
        team_id,
        player_id,
        minute,
        least(elapsed_end, (minute + 1) * 60) - greatest(elapsed_start, minute * 60) AS seconds
    FROM (
        SELECT
            *,
            UNNEST(range(
                CAST(floor(elapsed_start / 60.0) AS BIGINT),
                CAST(ceil(elapsed_end / 60.0) AS BIGINT)
            )) AS minute
        FROM players
    )
),

per_match AS (
    SELECT match_id, team_id, player_id, minute, sum(seconds) AS seconds
    FROM by_minute
    WHERE minute BETWEEN 0 AND 39
    GROUP BY match_id, team_id, player_id, minute
    HAVING sum(seconds) > 0
),

matches AS (
    SELECT
        match_id,
        edition_id,
        competition_id,
        round_type AS competition_phase
    FROM {{ ref('int_matches') }}
),

-- partidos del equipo con play-by-play en cada edición/competición/fase (denominador)
team_games AS (
    SELECT m.edition_id, m.competition_id, m.competition_phase, s.team_id, count(DISTINCT s.match_id) AS team_games
    FROM (
        SELECT match_id, home_team_id AS team_id FROM stints
        UNION
        SELECT match_id, away_team_id FROM stints
    ) s
    JOIN matches m USING (match_id)
    GROUP BY ALL
),

player_games AS (
    SELECT m.edition_id, m.competition_id, m.competition_phase, p.team_id, p.player_id,
           count(DISTINCT p.match_id) AS player_games
    FROM per_match p
    JOIN matches m USING (match_id)
    GROUP BY ALL
)

SELECT
    m.edition_id,
    m.competition_id,
    m.competition_phase,
    p.team_id,
    p.player_id,
    p.minute,
    count(*) AS games_on_court,
    sum(p.seconds) AS seconds_on_court,
    any_value(tg.team_games) AS team_games,
    any_value(pg.player_games) AS player_games,
    count(*) * 1.0 / NULLIF(any_value(tg.team_games), 0) AS pct_games_on_court,
    sum(p.seconds) * 1.0 / NULLIF(any_value(tg.team_games), 0) AS avg_seconds_on_court
FROM per_match p
JOIN matches m USING (match_id)
LEFT JOIN team_games tg
    ON tg.edition_id = m.edition_id
   AND tg.competition_id = m.competition_id
   AND tg.competition_phase = m.competition_phase
   AND tg.team_id = p.team_id
LEFT JOIN player_games pg
    ON pg.edition_id = m.edition_id
   AND pg.competition_id = m.competition_id
   AND pg.competition_phase = m.competition_phase
   AND pg.team_id = p.team_id
   AND pg.player_id = p.player_id
GROUP BY m.edition_id, m.competition_id, m.competition_phase, p.team_id, p.player_id, p.minute
