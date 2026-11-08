{{ config(
    materialized='table',
    schema = "intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'match_id', 'team_id']
) }}

-- Totales oficiales de equipo por partido (bloque `total` del boxscore, periodo 0), con las
-- estadísticas "de equipo" aparte para poder distinguirlas de la suma de jugadores.

WITH bt AS (
    SELECT *
    FROM {{ ref('stg_apiacb__boxscore_teams') }}
    WHERE quarter = 0
),

total AS (
    SELECT * FROM bt WHERE stat_scope = 'total'
),

team AS (
    SELECT * FROM bt WHERE stat_scope = 'team'
)

SELECT
    concat_ws('_', t.match_id, t.team_id) AS id,
    t.edition_id,
    t.match_id,
    t.team_id,
    t.club_id,

    t.points,
    t.free_throws_made,
    t.free_throws_attempted,
    t.two_pointers_made,
    t.two_pointers_attempted,
    t.three_pointers_made,
    t.three_pointers_attempted,
    t.dunks,
    t.assists,
    t.off_rebounds,
    t.def_rebounds,
    t.total_rebounds,
    t.steals,
    t.turnovers,
    t.blocks,
    t.received_blocks,
    t.personal_fouls,
    t.fouls_drawn,
    t.rating,

    coalesce(tm.off_rebounds, 0) AS team_off_rebounds,
    coalesce(tm.def_rebounds, 0) AS team_def_rebounds,
    coalesce(tm.turnovers, 0) AS team_turnovers,

    t.cat_insert_date

FROM total t
LEFT JOIN team tm
    ON tm.match_id = t.match_id
   AND tm.team_id = t.team_id
