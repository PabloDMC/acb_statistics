{{ config(
    materialized='table',
    schema = "staging",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'match_id']
) }}

-- Estadísticas de EQUIPO del boxscore, que stg_apiacb__boxscore (solo jugadores) no recoge.
-- Cada periodo trae dos bloques además de `players`:
--   total -> totales oficiales del equipo (jugadores + equipo)
--   team  -> lo que el acta asigna al equipo y a ningún jugador (rebotes y pérdidas de equipo)
-- Una fila por partido, equipo, periodo (0 = partido completo) y bloque.

WITH source AS (
    SELECT
        *,
        try_cast(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 1) AS INT) AS edition_id,
        try_cast(regexp_extract(filename, 'ed_(\d+)_m_(\d+)', 2) AS INT) AS match_id
    FROM {{ source('acb_landing', 'boxscores') }}
),

flattened_team_boxscores AS (
    SELECT
        edition_id,
        match_id,
        unnest(teamBoxscores) AS tb
    FROM source
),

flattened_periods AS (
    SELECT
        edition_id,
        match_id,
        try_cast(tb.team.id AS INT) AS team_id,
        try_cast(tb.team.clubId AS INT) AS club_id,
        unnest(tb.statsByPeriods) AS sbp
    FROM flattened_team_boxscores
),

blocks AS (
    SELECT edition_id, match_id, team_id, club_id,
           try_cast(sbp.quarter AS INT) AS quarter, 'total' AS stat_scope, sbp.stats.total AS s
    FROM flattened_periods

    UNION ALL

    SELECT edition_id, match_id, team_id, club_id,
           try_cast(sbp.quarter AS INT) AS quarter, 'team' AS stat_scope, sbp.stats.team AS s
    FROM flattened_periods
)

SELECT
    edition_id,
    match_id,
    team_id,
    club_id,
    quarter,
    stat_scope,
    try_cast(s.points AS INT) AS points,
    try_cast(s.freeThrowsMade AS INT) AS free_throws_made,
    try_cast(s.freeThrowsAttempted AS INT) AS free_throws_attempted,
    try_cast(s.twoPointersMade AS INT) AS two_pointers_made,
    try_cast(s.twoPointersAttempted AS INT) AS two_pointers_attempted,
    try_cast(s.threePointersMade AS INT) AS three_pointers_made,
    try_cast(s.threePointersAttempted AS INT) AS three_pointers_attempted,
    try_cast(s.dunks AS INT) AS dunks,
    try_cast(s.assists AS INT) AS assists,
    try_cast(s.offRebounds AS INT) AS off_rebounds,
    try_cast(s.defRebounds AS INT) AS def_rebounds,
    try_cast(s.totalRebounds AS INT) AS total_rebounds,
    try_cast(s.steals AS INT) AS steals,
    try_cast(s.turnovers AS INT) AS turnovers,
    try_cast(s.blocks AS INT) AS blocks,
    try_cast(s.receivedBlocks AS INT) AS received_blocks,
    try_cast(s.personalFouls AS INT) AS personal_fouls,
    try_cast(s.foulsDrawn AS INT) AS fouls_drawn,
    try_cast(s.rating AS INT) AS rating,
    current_timestamp AS cat_insert_date
FROM blocks
