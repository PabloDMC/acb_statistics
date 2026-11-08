{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH shots AS (

    SELECT
        *
    FROM {{ ref('int_shots') }}

),

zones AS (

    SELECT
        zone_id,
        shot_zone_basic,
        shot_zone_area,
        shot_zone_range
    FROM {{ ref('court_zones') }}

),

-- posesión y tramo del evento de play-by-play que corresponde al lanzamiento
events AS (

    SELECT
        match_id,
        event_idx,
        possession_seq AS possession_id,
        stint_seq AS stint_id
    FROM {{ ref('int_pbp_enriched') }}

),

joined AS (

    SELECT
        s.*,

        z.shot_zone_basic,
        z.shot_zone_area,
        z.shot_zone_range,

        e.possession_id,
        e.stint_id,

        -- El marcador del feed es el de después del lanzamiento: para la situación de partido
        -- se usa el de antes (un triple que pone +7 se lanzó con +4).
        s.score_home - CASE WHEN s.is_made AND s.team_id = s.home_team_id THEN s.shot_value ELSE 0 END
            AS score_home_before,
        s.score_away - CASE WHEN s.is_made AND s.team_id = s.away_team_id THEN s.shot_value ELSE 0 END
            AS score_away_before

    FROM shots s

    LEFT JOIN zones z
        USING (zone_id)

    LEFT JOIN events e
        ON e.match_id = s.match_id
       AND e.event_idx = s.event_idx

),

final AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,

        match_id,
        shot_id,
        event_idx,
        possession_id,
        stint_id,

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

        play_type_id,
        shot_value,
        is_made,
        is_dunk,
        is_assisted,
        is_and_one,

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

        abs(score_home_before - score_away_before) AS score_margin,

        (
            (quarter = 4 AND (minute * 60 + second) <= 300)
            OR quarter > 4
        )
        AND abs(score_home_before - score_away_before) <= 5 AS is_clutch,

        cat_insert_date

    FROM joined

)

SELECT *
FROM final
