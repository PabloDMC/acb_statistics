{{ config(
    materialized='table',
    schema='intermediate',
    tags=['acb_analytics'],
    cluster_by=['match_id']
) }}

-- Una fila por posesión: racha de eventos marcadores del mismo equipo dentro de un cuarto
-- (ver int_pbp_enriched). Los puntos son los anotados mientras dura la posesión: `points` los
-- del equipo que ataca y `opponent_points` los del rival (solo tiros libres de técnica).

WITH ev AS (
    SELECT
        p.match_id,
        p.event_idx,
        p.quarter,
        p.seconds_remaining,
        p.play_type_id,
        p.team_id,
        p.home_team_id,
        p.away_team_id,
        p.points,
        p.score_home,
        p.score_away,
        p.is_clutch,
        e.is_offense_marker,
        e.offense_team_id,
        e.possession_seq,
        e.stint_seq,
        e.home_lineup,
        e.away_lineup
    FROM {{ ref('int_play_by_play') }} p
    JOIN {{ ref('int_pbp_enriched') }} e
        USING (match_id, event_idx)
),

markers AS (
    SELECT
        match_id,
        quarter,
        possession_seq,
        any_value(offense_team_id) AS team_id,
        any_value(home_team_id) AS home_team_id,
        any_value(away_team_id) AS away_team_id,
        min(event_idx) AS start_event_idx,
        max(event_idx) AS end_event_idx,
        arg_min(seconds_remaining, event_idx) AS start_time,
        arg_max(seconds_remaining, event_idx) AS end_time,
        arg_min(play_type_id, event_idx) AS first_play_type_id,
        arg_max(play_type_id, event_idx) AS end_play_type_id,
        count(*) AS n_markers,
        -- quintetos, tramo y situación de partido al terminar la posesión
        arg_max(stint_seq, event_idx) AS stint_seq,
        arg_max(home_lineup, event_idx) AS home_lineup,
        arg_max(away_lineup, event_idx) AS away_lineup,
        arg_max(score_home, event_idx) AS score_home_end,
        arg_max(score_away, event_idx) AS score_away_end,
        bool_or(is_clutch) AS is_clutch
    FROM ev
    WHERE is_offense_marker
    GROUP BY match_id, quarter, possession_seq
),

scoring AS (
    SELECT
        match_id,
        possession_seq,
        sum(CASE WHEN team_id = offense_team_id THEN points ELSE 0 END) AS points,
        sum(CASE WHEN team_id <> offense_team_id THEN points ELSE 0 END) AS opponent_points
    FROM ev
    WHERE points > 0
    GROUP BY match_id, possession_seq
)

SELECT
    concat_ws('_', m.match_id, m.possession_seq) AS id,
    m.match_id,
    m.quarter,
    m.possession_seq,
    m.team_id,
    CASE WHEN m.team_id = m.home_team_id THEN m.away_team_id ELSE m.home_team_id END AS opponent_team_id,
    m.home_team_id,
    m.away_team_id,
    m.start_event_idx,
    m.end_event_idx,
    m.start_time,
    m.end_time,
    coalesce(s.points, 0) AS points,
    coalesce(s.opponent_points, 0) AS opponent_points,
    m.end_play_type_id,
    CASE
        WHEN m.end_play_type_id IN (93, 94, 100) THEN 'made_field_goal'
        WHEN m.end_play_type_id IN (97, 98, 533) THEN 'missed_field_goal'
        WHEN m.end_play_type_id IN (92, 96) THEN 'free_throws'
        WHEN m.end_play_type_id = 106 THEN 'turnover'
        ELSE 'end_of_period'
    END AS end_reason,
    m.n_markers,
    m.stint_seq,
    m.home_lineup,
    m.away_lineup,
    m.score_home_end,
    m.score_away_end,
    m.is_clutch,
    -- Un rebote defensivo con 3 segundos o menos por jugar y nada más no llega a ser posesión,
    -- pero solo si es lo último del cuarto: si después ataca el rival, el balón cambió de manos
    -- (el feed a veces no apunta cómo) y descartarla dejaba al rival con dos posesiones seguidas
    -- (partido 103869, 1er cuarto).
    NOT (
        m.n_markers = 1
        AND m.first_play_type_id = 104
        AND m.start_time <= 3
        AND m.possession_seq = max(m.possession_seq) OVER (PARTITION BY m.match_id, m.quarter)
    ) AS is_counted
FROM markers m
LEFT JOIN scoring s
    ON s.match_id = m.match_id
   AND s.possession_seq = m.possession_seq
