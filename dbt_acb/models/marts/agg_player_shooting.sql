{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH pbp AS (

    SELECT
        match_id,
        quarter,
        minute,
        second,
        player_id,
        team_id,
        play_type_id,

        LEAD(play_type_id,1) OVER(
            PARTITION BY match_id
            ORDER BY event_order
        ) AS next_play_1,

        LEAD(play_type_id,2) OVER(
            PARTITION BY match_id
            ORDER BY event_order
        ) AS next_play_2,

        LEAD(play_type_id,3) OVER(
            PARTITION BY match_id
            ORDER BY event_order
        ) AS next_play_3

    FROM {{ ref('int_play_by_play') }}

),

shots AS (

    SELECT

        s.*,

        CASE
            WHEN p.play_type_id IN (100,533)
            THEN 1
            ELSE 0
        END AS is_dunk,

        CASE
            WHEN p.next_play_1 IN (107,108)
            THEN 1
            ELSE 0
        END AS assisted_fg,

        CASE
            WHEN
                p.next_play_1 IN (160,161,162,163)
                OR p.next_play_2 IN (160,161,162,163)
                OR p.next_play_3 IN (160,161,162,163)
            THEN 1
            ELSE 0
        END AS and_one

    FROM {{ ref('fact_shots') }} s

    LEFT JOIN pbp p
    USING(
        match_id,
        quarter,
        minute,
        second,
        player_id,
        team_id
    )

),

totals AS (

SELECT

    edition_id,
    competition_id,
    competition_phase,

    player_id,
    team_id,
    club_id,

    -----------------------------------
    -- GENERAL
    -----------------------------------

    SUM(CASE WHEN zone_id<>14 THEN 1 ELSE 0 END) AS field_goals_attempted,
    SUM(CASE WHEN zone_id<>14 AND is_made THEN 1 ELSE 0 END) AS field_goals_made,

    SUM(CASE WHEN zone_id=14 THEN 1 ELSE 0 END) AS free_throws_attempted,
    SUM(CASE WHEN zone_id=14 AND is_made THEN 1 ELSE 0 END) AS free_throws_made,

    SUM(CASE WHEN shot_value=2 THEN 1 ELSE 0 END) AS two_pointers_attempted,
    SUM(CASE WHEN shot_value=2 AND is_made THEN 1 ELSE 0 END) AS two_pointers_made,

    SUM(CASE WHEN shot_value=3 THEN 1 ELSE 0 END) AS three_pointers_attempted,
    SUM(CASE WHEN shot_value=3 AND is_made THEN 1 ELSE 0 END) AS three_pointers_made,

    SUM(CASE WHEN is_dunk THEN 1 ELSE 0 END) AS dunks_attempted,
    SUM(CASE WHEN is_dunk AND is_made THEN 1 ELSE 0 END) AS dunks_made,

    -----------------------------------
    -- ZONES
    -----------------------------------

    SUM(CASE WHEN zone_id=1 THEN 1 ELSE 0 END) AS restricted_attempted,
    SUM(CASE WHEN zone_id=1 AND is_made THEN 1 ELSE 0 END) AS restricted_made,

    SUM(CASE WHEN zone_id IN (2,3,4) THEN 1 ELSE 0 END) AS paint_attempted,
    SUM(CASE WHEN zone_id IN (2,3,4) AND is_made THEN 1 ELSE 0 END) AS paint_made,

    SUM(CASE WHEN zone_id IN (5,6,7) THEN 1 ELSE 0 END) AS midrange_attempted,
    SUM(CASE WHEN zone_id IN (5,6,7) AND is_made THEN 1 ELSE 0 END) AS midrange_made,

    SUM(CASE WHEN zone_id IN (8,9) THEN 1 ELSE 0 END) AS corner_three_attempted,
    SUM(CASE WHEN zone_id IN (8,9) AND is_made THEN 1 ELSE 0 END) AS corner_three_made,

    SUM(CASE WHEN zone_id IN (10,11,12) THEN 1 ELSE 0 END) AS above_break_three_attempted,
    SUM(CASE WHEN zone_id IN (10,11,12) AND is_made THEN 1 ELSE 0 END) AS above_break_three_made,

    SUM(CASE WHEN zone_id=13 THEN 1 ELSE 0 END) AS half_court_attempted,
    SUM(CASE WHEN zone_id=13 AND is_made THEN 1 ELSE 0 END) AS half_court_made,

    -----------------------------------
    -- CREATION
    -----------------------------------

    SUM(CASE WHEN is_made THEN assisted_fg ELSE 0 END) AS assisted_field_goals_made,

    SUM(CASE WHEN is_made THEN 1-assisted_fg ELSE 0 END) AS unassisted_field_goals_made,

    SUM(CASE WHEN shot_value=2 AND is_made THEN assisted_fg ELSE 0 END) AS assisted_two_pointers_made,

    SUM(CASE WHEN shot_value=3 AND is_made THEN assisted_fg ELSE 0 END) AS assisted_three_pointers_made,

    SUM(CASE WHEN is_dunk AND is_made AND assisted_fg=1 THEN 1 ELSE 0 END) AS assisted_dunks,

    SUM(CASE WHEN is_dunk AND is_made AND assisted_fg=0 THEN 1 ELSE 0 END) AS unassisted_dunks,

    SUM(CASE WHEN is_made THEN and_one ELSE 0 END) AS and_ones

FROM shots

GROUP BY ALL

)

SELECT

    *,

    -----------------------------------
    -- GENERAL %
    -----------------------------------

    field_goals_made / NULLIF(field_goals_attempted,0) AS field_goals_pct,

    free_throws_made / NULLIF(free_throws_attempted,0) AS free_throws_pct,

    two_pointers_made / NULLIF(two_pointers_attempted,0) AS two_pointers_pct,

    three_pointers_made / NULLIF(three_pointers_attempted,0) AS three_pointers_pct,

    dunks_made / NULLIF(dunks_attempted,0) AS dunks_pct,

    -----------------------------------
    -- SHOT PROFILE
    -----------------------------------

    restricted_made / NULLIF(restricted_attempted,0) AS restricted_pct,
    paint_made / NULLIF(paint_attempted,0) AS paint_pct,
    midrange_made / NULLIF(midrange_attempted,0) AS midrange_pct,
    corner_three_made / NULLIF(corner_three_attempted,0) AS corner_three_pct,
    above_break_three_made / NULLIF(above_break_three_attempted,0) AS above_break_three_pct,
    half_court_made / NULLIF(half_court_attempted,0) AS half_court_pct,

    restricted_attempted / NULLIF(field_goals_attempted,0) AS restricted_frequency,
    paint_attempted / NULLIF(field_goals_attempted,0) AS paint_frequency,
    midrange_attempted / NULLIF(field_goals_attempted,0) AS midrange_frequency,
    corner_three_attempted / NULLIF(field_goals_attempted,0) AS corner_three_frequency,
    above_break_three_attempted / NULLIF(field_goals_attempted,0) AS above_break_three_frequency,
    half_court_attempted / NULLIF(field_goals_attempted,0) AS half_court_frequency,

    two_pointers_attempted / NULLIF(field_goals_attempted,0) AS two_pointers_frequency,
    three_pointers_attempted / NULLIF(field_goals_attempted,0) AS three_pointers_frequency,

    -----------------------------------
    -- CREATION
    -----------------------------------

    assisted_field_goals_made / NULLIF(field_goals_made,0) AS assisted_field_goals_pct,

    unassisted_field_goals_made / NULLIF(field_goals_made,0) AS unassisted_field_goals_pct,

    assisted_two_pointers_made / NULLIF(two_pointers_made,0) AS assisted_two_pointers_pct,

    assisted_three_pointers_made / NULLIF(three_pointers_made,0) AS assisted_three_pointers_pct,

    assisted_dunks / NULLIF(dunks_made,0) AS assisted_dunks_pct,

    unassisted_dunks / NULLIF(dunks_made,0) AS unassisted_dunks_pct

FROM totals
