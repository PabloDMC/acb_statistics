{{ config(
    materialized='incremental',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH st AS (

    SELECT
        match_id,
        team_id,
        stint_id,
        quarter,
        start_time,
        end_time,
        score_h_start,
        score_h_end,
        score_a_start,
        score_a_end,
        player_ids
    FROM {{ ref('int_lineups') }}

    {% if is_incremental() %}
    WHERE match_id NOT IN (
        SELECT DISTINCT match_id
        FROM {{ this }}
    )
    {% endif %}

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
        st.*,

        m.edition_id,
        m.competition_id,
        m.competition_phase,

        m.home_team_id,
        m.home_team_club_id,
        m.away_team_id,
        m.away_team_club_id,

        CASE
            WHEN st.team_id = m.home_team_id THEN m.home_team_club_id
            ELSE m.away_team_club_id
        END AS club_id,

        CASE
            WHEN st.team_id = m.home_team_id THEN m.home_team_full_name
            ELSE m.away_team_full_name
        END AS team_full_name

    FROM st

    LEFT JOIN m
    USING(match_id)

),

scoring AS (

    SELECT

        *,

        CASE
            WHEN team_id = home_team_id THEN score_h_start
            ELSE score_a_start
        END AS score_team_start,

        CASE
            WHEN team_id = home_team_id THEN score_h_end
            ELSE score_a_end
        END AS score_team_end,

        CASE
            WHEN team_id = home_team_id THEN score_a_start
            ELSE score_h_start
        END AS score_opp_start,

        CASE
            WHEN team_id = home_team_id THEN score_a_end
            ELSE score_h_end
        END AS score_opp_end,

        start_time-end_time AS duration_seconds

    FROM joined

),

poss AS (

    SELECT

        p.*,

        m.home_team_id,

        CASE
            WHEN p.team_id = m.home_team_id THEN p.score_h_start
            ELSE p.score_a_start
        END AS score_team_start,

        CASE
            WHEN p.team_id = m.home_team_id THEN p.score_h_end
            ELSE p.score_a_end
        END AS score_team_end,

        CASE
            WHEN p.team_id = m.home_team_id THEN p.score_a_start
            ELSE p.score_h_start
        END AS score_opp_start,

        CASE
            WHEN p.team_id = m.home_team_id THEN p.score_a_end
            ELSE p.score_h_end
        END AS score_opp_end

    FROM {{ ref('int_possessions') }} p
    LEFT JOIN m USING(match_id)
    WHERE p.start_time > p.end_time

),

possessions AS (

    SELECT

        s.match_id,
        s.team_id,
        s.stint_id,

        COUNT_IF(p.team_id = s.team_id) AS offensive_possessions,
        COUNT_IF(p.team_id <> s.team_id) AS defensive_possessions,

        SUM(
            CASE
                WHEN p.team_id = s.team_id THEN p.score_team_end - p.score_team_start
                ELSE 0
            END
        ) AS team_points,

        SUM(
            CASE
                WHEN p.team_id <> s.team_id THEN p.score_team_end - p.score_team_start
                ELSE 0
            END
        ) AS opp_points

    FROM scoring s
    LEFT JOIN poss p
        ON p.match_id = s.match_id
       AND p.quarter = s.quarter
       AND p.start_time <= s.start_time
       AND p.end_time >= s.end_time
    GROUP BY
        s.match_id,
        s.team_id,
        s.stint_id

)

SELECT

    s.edition_id,
    s.competition_id,
    s.competition_phase,

    s.match_id,

    s.team_id,
    s.club_id,
    s.team_full_name,

    s.quarter,

    s.stint_id,

    s.start_time,
    s.end_time,

    s.duration_seconds,

    s.score_team_start,
    s.score_team_end,

    s.score_opp_start,
    s.score_opp_end,

    (s.score_team_end-s.score_team_start) - (s.score_opp_end-s.score_opp_start) AS plus_minus,

    COALESCE(p.offensive_possessions,0) AS offensive_possessions,
    COALESCE(p.defensive_possessions,0) AS defensive_possessions,
    COALESCE(p.offensive_possessions,0) + COALESCE(p.defensive_possessions,0) AS total_possessions,
    COALESCE(p.team_points,0) AS team_points,
    COALESCE(p.opp_points,0) AS opp_points,

    s.player_ids

FROM scoring s

LEFT JOIN possessions p
ON s.match_id=p.match_id
AND s.team_id=p.team_id
AND s.stint_id=p.stint_id