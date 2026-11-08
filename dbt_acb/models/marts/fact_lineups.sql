{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Una fila por tramo y equipo: los 5 jugadores del equipo y los 5 del rival mientras ninguno de
-- los 10 cambia. Cada tramo de int_stints da dos filas (local y visitante), de modo que
--   suma de offensive_possessions / team_points de un equipo = sus totales del partido.
-- start_time y end_time son segundos RESTANTES del cuarto (start_time > end_time).

WITH st AS (
    SELECT *
    FROM {{ ref('int_stints') }}
),

m AS (
    SELECT
        match_id,
        edition_id,
        competition_id,
        round_type AS competition_phase,
        home_team_club_id,
        away_team_club_id,
        home_team_full_name,
        away_team_full_name
    FROM {{ ref('int_matches') }}
),

sides AS (
    SELECT
        st.match_id, st.quarter, st.stint_seq, st.start_time, st.end_time, st.seconds,
        TRUE AS is_home,
        st.home_team_id AS team_id,
        st.away_team_id AS opponent_team_id,
        st.home_player_ids AS player_ids,
        st.away_player_ids AS opponent_player_ids,
        st.home_points AS team_points,
        st.away_points AS opp_points,
        st.home_possessions AS offensive_possessions,
        st.away_possessions AS defensive_possessions
    FROM st

    UNION ALL

    SELECT
        st.match_id, st.quarter, st.stint_seq, st.start_time, st.end_time, st.seconds,
        FALSE AS is_home,
        st.away_team_id,
        st.home_team_id,
        st.away_player_ids,
        st.home_player_ids,
        st.away_points,
        st.home_points,
        st.away_possessions,
        st.home_possessions
    FROM st
)

SELECT

    m.edition_id,
    m.competition_id,
    m.competition_phase,

    s.match_id,

    s.team_id,
    CASE WHEN s.is_home THEN m.home_team_club_id ELSE m.away_team_club_id END AS club_id,
    CASE WHEN s.is_home THEN m.home_team_full_name ELSE m.away_team_full_name END AS team_full_name,
    s.opponent_team_id,
    s.is_home,

    s.quarter,

    s.stint_seq AS stint_id,

    s.start_time,
    s.end_time,

    s.seconds AS duration_seconds,

    s.team_points,
    s.opp_points,
    s.team_points - s.opp_points AS plus_minus,

    s.offensive_possessions,
    s.defensive_possessions,
    s.offensive_possessions + s.defensive_possessions AS total_possessions,

    s.player_ids,
    s.opponent_player_ids

FROM sides s
LEFT JOIN m USING (match_id)
