{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Una fila por posesión contada. possession_id es único dentro del partido.

WITH poss AS (
    SELECT *
    FROM {{ ref('int_possessions') }}
    WHERE is_counted
),

m AS (
    SELECT
        match_id,
        edition_id,
        competition_id,
        round_type AS competition_phase,
        home_team_id,
        home_team_club_id,
        away_team_id,
        away_team_club_id,
        home_team_full_name,
        away_team_full_name
    FROM {{ ref('int_matches') }}
),

joined AS (
    SELECT
        p.*,
        m.edition_id,
        m.competition_id,
        m.competition_phase,
        (p.team_id = m.home_team_id) AS is_home,
        CASE WHEN p.team_id = m.home_team_id THEN m.home_team_club_id ELSE m.away_team_club_id END AS club_id,
        CASE WHEN p.team_id = m.home_team_id THEN m.away_team_club_id ELSE m.home_team_club_id END AS opponent_club_id,
        CASE WHEN p.team_id = m.home_team_id THEN m.home_team_full_name ELSE m.away_team_full_name END AS team_full_name,
        -- la posesión empieza donde acabó la anterior del cuarto (o con el cuarto)
        coalesce(
            lag(p.end_time) OVER (PARTITION BY p.match_id, p.quarter ORDER BY p.possession_seq),
            CASE WHEN p.quarter <= 4 THEN 600 ELSE 300 END
        ) AS possession_start_time
    FROM poss p
    LEFT JOIN m USING (match_id)
)

SELECT
    j.id,
    j.edition_id,
    j.competition_id,
    j.competition_phase,
    j.match_id,
    j.team_id,
    j.club_id,
    j.team_full_name,
    j.opponent_team_id,
    j.opponent_club_id,
    j.is_home,
    j.quarter,
    j.possession_seq AS possession_id,
    j.possession_start_time AS start_time,
    j.end_time,
    greatest(j.possession_start_time - j.end_time, 0) AS duration_seconds,
    j.points,
    j.opponent_points,
    CASE WHEN j.is_home THEN j.score_home_end ELSE j.score_away_end END AS score_team_end,
    CASE WHEN j.is_home THEN j.score_away_end ELSE j.score_home_end END AS score_opp_end,
    j.end_play_type_id,
    j.end_reason,
    j.is_clutch,
    j.stint_seq AS stint_id,
    CASE WHEN j.is_home THEN s.home_player_ids ELSE s.away_player_ids END AS player_ids,
    CASE WHEN j.is_home THEN s.away_player_ids ELSE s.home_player_ids END AS opponent_player_ids
FROM joined j
LEFT JOIN {{ ref('int_stints') }} s
    ON s.match_id = j.match_id
   AND s.stint_seq = j.stint_seq
