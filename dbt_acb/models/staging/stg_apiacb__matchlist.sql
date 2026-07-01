{{ config(
    materialized='table',
    schema = "staging",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'match_id']
) }}

WITH flattened AS (
    SELECT
        try_cast(editionId AS INT) AS edition_id,
        --try_cast(competitionId AS INT) AS competition_id,
        try_cast(matchGrouping AS VARCHAR) AS match_grouping,
        unnest(matches) AS m
    FROM {{ source('acb_landing', 'matchlists') }}
)

SELECT
    edition_id,
    --competition_id,
    match_grouping,
    try_cast(m.id AS INT) AS match_id,
    try_cast(m.roundType AS VARCHAR) AS round_type,
    try_cast(m.roundId AS INT) AS round_id,
    try_cast(m.roundNumber AS INT) AS round_number,
    try_cast(m.groupId AS INT) AS group_id,
    try_cast(m.subphaseId AS INT) AS subphase_id,
    try_cast(m.subphaseNumber AS INT) AS subphase_number,
    try_cast(m.weekId AS INT) AS week_id,
    try_cast(m.homeClubId AS INT) AS home_club_id,
    try_cast(m.awayClubId AS INT) AS away_club_id,
    try_cast(m.homeTeam.id AS INT) AS home_team_id,
    try_cast(m.awayTeam.id AS INT) AS away_team_id,
    try_cast(m.homeCurrentWins AS INT) AS home_current_wins,
    try_cast(m.homeCurrentLosses AS INT) AS home_current_losses,
    try_cast(m.awayCurrentWins AS INT) AS away_current_wins,
    try_cast(m.awayCurrentLosses AS INT) AS away_current_losses,
    try_cast(m ->> 'serieData' AS VARCHAR) AS playoff_serie_data,
    current_timestamp AS cat_insert_date
FROM flattened