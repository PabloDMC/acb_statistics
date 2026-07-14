{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH shots AS (

    SELECT *
    FROM {{ ref('fact_shots') }}

),

zones AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,

        player_id,
        team_id,
        club_id,

        zone_id,
        shot_zone_basic,
        shot_zone_area,
        shot_zone_range,

        COUNT(*) AS field_goals_attempted,
        SUM(is_made) AS field_goals_made

    FROM shots

    WHERE zone_id <> 14

    GROUP BY ALL

)

SELECT

    *,

    field_goals_made::DOUBLE
        / NULLIF(field_goals_attempted,0)
        AS field_goals_pct,

    field_goals_attempted::DOUBLE
        /
        SUM(field_goals_attempted) OVER (
            PARTITION BY
                edition_id,
                competition_id,
                competition_phase,
                player_id,
                team_id,
                club_id
        )
        AS field_goal_frequency

FROM zones