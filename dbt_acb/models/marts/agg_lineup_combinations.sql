{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH lineups AS (

    SELECT *

    FROM {{ ref('fact_lineups') }}

),

--========================
-- PAIRS (C(5,2)=10)
--========================

pairs AS (

    SELECT

        l.edition_id,
        l.competition_id,
        l.competition_phase,

        l.match_id,

        l.club_id,
        l.team_id,

        l.duration_seconds,

        l.offensive_possessions,
        l.defensive_possessions,
        l.total_possessions,

        l.team_points,
        l.opp_points,

        l.plus_minus,

        2 AS player_count,

        list_sort(list_value(p1.player_id,p2.player_id)) AS player_ids

    FROM lineups l

    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p1(player_id,pos1)
    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p2(player_id,pos2)

    WHERE pos1 < pos2

),

--========================
-- TRIOS (C(5,3)=10)
--========================

trios AS (

    SELECT

        l.edition_id,
        l.competition_id,
        l.competition_phase,

        l.match_id,

        l.club_id,
        l.team_id,

        l.duration_seconds,

        l.offensive_possessions,
        l.defensive_possessions,
        l.total_possessions,

        l.team_points,
        l.opp_points,

        l.plus_minus,

        3 AS player_count,

        list_sort(
            list_value(
                p1.player_id,
                p2.player_id,
                p3.player_id
            )
        ) AS player_ids

    FROM lineups l

    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p1(player_id,pos1)
    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p2(player_id,pos2)
    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p3(player_id,pos3)

    WHERE pos1 < pos2
      AND pos2 < pos3

),

--========================
-- QUARTETS (C(5,4)=5)
--========================

quartets AS (

    SELECT

        l.edition_id,
        l.competition_id,
        l.competition_phase,

        l.match_id,

        l.club_id,
        l.team_id,

        l.duration_seconds,

        l.offensive_possessions,
        l.defensive_possessions,
        l.total_possessions,

        l.team_points,
        l.opp_points,

        l.plus_minus,

        4 AS player_count,

        list_sort(
            list_value(
                p1.player_id,
                p2.player_id,
                p3.player_id,
                p4.player_id
            )
        ) AS player_ids

    FROM lineups l

    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p1(player_id,pos1)
    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p2(player_id,pos2)
    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p3(player_id,pos3)
    CROSS JOIN UNNEST(l.player_ids) WITH ORDINALITY AS p4(player_id,pos4)

    WHERE pos1 < pos2
      AND pos2 < pos3
      AND pos3 < pos4

),

--========================
-- QUINTETS
--========================

quintets AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,

        match_id,

        club_id,
        team_id,

        duration_seconds,

        offensive_possessions,
        defensive_possessions,
        total_possessions,

        team_points,
        opp_points,

        plus_minus,

        5 AS player_count,

        list_sort(player_ids) AS player_ids

    FROM lineups

),

all_combinations AS (

    SELECT * FROM pairs

    UNION ALL

    SELECT * FROM trios

    UNION ALL

    SELECT * FROM quartets

    UNION ALL

    SELECT * FROM quintets

),

agg AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,

        club_id,
        team_id,

        player_count,
        player_ids,

        COUNT(DISTINCT match_id) AS games,

        COUNT(*) AS stints,

        SUM(duration_seconds) AS seconds,

        SUM(offensive_possessions) AS offensive_possessions,
        SUM(defensive_possessions) AS defensive_possessions,
        SUM(total_possessions) AS possessions,

        SUM(team_points) AS team_points,
        SUM(opp_points) AS opp_points,

        SUM(plus_minus) AS plus_minus

    FROM all_combinations

    GROUP BY ALL

)

SELECT

    *,

    seconds/60.0 AS minutes,

    100.0*team_points/NULLIF(offensive_possessions,0)
        AS offensive_rating,

    100.0*opp_points/NULLIF(defensive_possessions,0)
        AS defensive_rating,

    100.0*team_points/NULLIF(offensive_possessions,0)
    -
    100.0*opp_points/NULLIF(defensive_possessions,0)
        AS net_rating

FROM agg