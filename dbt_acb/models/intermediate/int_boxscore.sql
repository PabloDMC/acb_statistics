{{ config(
    materialized='table',
    schema = "intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'competition_id', 'match_id', 'player_id']
) }}

WITH bs AS (
    SELECT *
    FROM {{ ref('stg_apiacb__boxscore') }}
),

mh AS (
    SELECT
        match_id,
        competition_id
    FROM {{ ref('stg_apiacb__match_header') }}
),

players_clean AS (
    SELECT *
    FROM bs
    WHERE quarter = 0
),

players_ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY edition_id, match_id, player_id
            ORDER BY match_id DESC
        ) AS rn
    FROM players_clean
)

SELECT
    pr.edition_id,
    pr.match_id,
    mh.competition_id,
    pr.team_id,
    pr.club_id,
    pr.player_id,

    pr.player_game_role,
    pr.is_starter,
    pr.play_time,

    pr.points,
    pr.free_throws_made,
    pr.free_throws_attempted,
    pr.two_pointers_made,
    pr.two_pointers_attempted,
    pr.three_pointers_made,
    pr.three_pointers_attempted,
    pr.dunks,
    pr.assists,
    pr.off_rebounds,
    pr.def_rebounds,
    pr.total_rebounds,
    pr.steals,
    pr.turnovers,
    pr.blocks,
    pr.received_blocks,
    pr.personal_fouls,
    pr.fouls_drawn,
    pr.plus_minus,
    pr.rating,

    pr.cat_insert_date

FROM players_ranked pr
LEFT JOIN mh USING (match_id)
WHERE rn = 1