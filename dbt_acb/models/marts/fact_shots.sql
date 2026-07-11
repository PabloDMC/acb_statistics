{{ config(
    materialized='incremental',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH shots AS (

    SELECT
        *
    FROM {{ ref('int_shots') }}

    {% if is_incremental() %}
    WHERE match_id NOT IN (
        SELECT DISTINCT match_id
        FROM {{ this }}
    )
    {% endif %}

),

matches AS (

    SELECT
        match_id,
        home_team_id,
        away_team_id
    FROM {{ ref('int_matches') }}

),

zones AS (

    SELECT
        zone_id,
        shot_zone_basic,
        shot_zone_area,
        shot_zone_range
    FROM {{ ref('court_zones') }}

),

joined AS (

    SELECT
        s.*,

        m.home_team_id,
        m.away_team_id,

        z.shot_zone_basic,
        z.shot_zone_area,
        z.shot_zone_range

    FROM shots s

    LEFT JOIN matches m
        USING (match_id)

    LEFT JOIN zones z
        USING (zone_id)

),

final AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,

        match_id,
        shot_id,

        player_id,
        team_id,
        club_id,

        quarter,
        minute,
        second,
        minute * 60 + second AS seconds_remaining,

        x,
        y,

        distance_mm,
        angle_deg,

        zone_id,
        shot_zone_basic,
        shot_zone_area,
        shot_zone_range,

        shot_value,
        is_made,

        CASE
            WHEN team_id = home_team_id
                THEN score_home
            ELSE score_away
        END AS score_team,

        CASE
            WHEN team_id = home_team_id
                THEN score_away
            ELSE score_home
        END AS score_opp,

        abs(score_home - score_away) AS score_margin,

        CASE
            WHEN
                (
                    (quarter = 4 AND (minute * 60 + second) <= 300)
                    OR quarter > 4
                )
                AND abs(score_home - score_away) <= 5
            THEN TRUE
            ELSE FALSE
        END AS is_clutch,

        cat_insert_date

    FROM joined

)

SELECT *
FROM final