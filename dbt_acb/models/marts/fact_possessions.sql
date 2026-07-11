{{ config(
    materialized='incremental',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH poss AS (

    SELECT
        match_id,
        quarter,
        possession_id,
        team_id,
        start_time,
        end_time,
        score_h_start,
        score_h_end,
        score_a_start,
        score_a_end,
        end_reason
    FROM {{ ref('int_possessions') }}

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
        round_type as competition_phase,
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
        m.home_team_id,
        m.home_team_club_id,
        m.away_team_id,
        m.away_team_club_id,
        m.home_team_full_name,
        m.away_team_full_name,

        CASE WHEN p.team_id = m.home_team_id THEN m.home_team_club_id
             ELSE m.away_team_club_id
        END AS club_id,

        CASE WHEN p.team_id = m.home_team_id THEN m.home_team_full_name
             ELSE m.away_team_full_name
        END AS team_full_name,

        pt.play_name,

        l.stint_id,
        l.player_ids

    FROM poss p
    LEFT JOIN m USING (match_id)
    LEFT JOIN {{ ref('play_types') }} pt 
    ON pt.play_type_id = p.end_reason
    LEFT JOIN {{ ref('int_lineups') }} l
    ON p.match_id = l.match_id
    AND p.team_id  = l.team_id
    AND p.quarter  = l.quarter
    AND p.start_time <= l.start_time
    AND p.start_time > l.end_time
),

scoring AS (
    SELECT
        *,
        CASE WHEN team_id = home_team_id THEN score_h_start ELSE score_a_start END AS score_team_start,
        CASE WHEN team_id = home_team_id THEN score_h_end   ELSE score_a_end   END AS score_team_end,
        CASE WHEN team_id = home_team_id THEN score_a_start ELSE score_h_start END AS score_opp_start,
        CASE WHEN team_id = home_team_id THEN score_a_end   ELSE score_h_end   END AS score_opp_end,

        (
            (CASE WHEN team_id = home_team_id THEN score_h_end ELSE score_a_end END)
            -
            (CASE WHEN team_id = home_team_id THEN score_h_start ELSE score_a_start END)
        )
        -
        (
            (CASE WHEN team_id = home_team_id THEN score_a_end ELSE score_h_end END)
            -
            (CASE WHEN team_id = home_team_id THEN score_a_start ELSE score_h_start END)
        ) AS plus_minus,

        start_time - end_time AS duration_seconds
    FROM joined
)

SELECT
    edition_id,
    competition_id,
    competition_phase,
    match_id,
    team_id,
    club_id,
    team_full_name,
    quarter,
    possession_id,
    start_time,
    end_time,
    duration_seconds,
    score_team_start,
    score_team_end,
    score_opp_start,
    score_opp_end,
    plus_minus,
    stint_id,
    player_ids,
    end_reason,
    play_name as end_reason_desc
FROM scoring
where start_time > end_time