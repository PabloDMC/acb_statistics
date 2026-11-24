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
        mh.match_id,
        mh.competition_id,
        ml.round_type as competition_phase
    FROM {{ ref('stg_apiacb__matchlist') }} ml
    JOIN {{ ref('stg_apiacb__match_header') }} mh USING (match_id)
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
    concat_ws('_', pr.match_id, pr.player_id) AS id,

    pr.edition_id,
    pr.match_id,
    mh.competition_id,
    mh.competition_phase,
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
    -- Estadísticas que en temporadas antiguas no se registraban: si en toda la temporada y competición suman 0,
    -- se dejan en NULL (sin dato) para que no cuenten como ceros en medias y récords. Con abs():
    -- el +/- de todos los jugadores de una temporada suma 0 por definición.
    CASE WHEN sum(abs(coalesce(pr.dunks, 0))) OVER (PARTITION BY pr.edition_id, mh.competition_id) = 0 THEN NULL ELSE pr.dunks END AS dunks,
    pr.assists,
    pr.off_rebounds,
    pr.def_rebounds,
    pr.total_rebounds,
    pr.steals,
    pr.turnovers,
    pr.blocks,
    CASE WHEN sum(abs(coalesce(pr.received_blocks, 0))) OVER (PARTITION BY pr.edition_id, mh.competition_id) = 0 THEN NULL ELSE pr.received_blocks END AS received_blocks,
    pr.personal_fouls,
    CASE WHEN sum(abs(coalesce(pr.fouls_drawn, 0))) OVER (PARTITION BY pr.edition_id, mh.competition_id) = 0 THEN NULL ELSE pr.fouls_drawn END AS fouls_drawn,
    CASE WHEN sum(abs(coalesce(pr.plus_minus, 0))) OVER (PARTITION BY pr.edition_id, mh.competition_id) = 0 THEN NULL ELSE pr.plus_minus END AS plus_minus,
    pr.rating,

    pr.cat_insert_date

FROM players_ranked pr
LEFT JOIN mh USING (match_id)
WHERE rn = 1