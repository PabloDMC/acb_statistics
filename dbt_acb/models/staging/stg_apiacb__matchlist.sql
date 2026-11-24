{{ config(
    materialized='table',
    schema = "staging",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'match_id']
) }}

WITH flattened AS (
    -- el source es JSON crudo (una fila por fichero, columna `json`): ver sources.yml
    SELECT
        try_cast("json" ->> 'editionId' AS INT) AS edition_id,
        try_cast("json" ->> 'competitionId' AS INT) AS competition_id,
        "json" ->> 'matchGrouping' AS match_grouping,
        unnest(json_extract("json", '$.matches[*]')) AS m
    FROM {{ source('acb_landing', 'matchlists') }}
)

SELECT
    edition_id,
    competition_id,
    match_grouping,
    try_cast(m ->> 'id' AS INT) AS match_id,
    m ->> 'roundType' AS round_type,
    try_cast(m ->> 'roundId' AS INT) AS round_id,
    try_cast(m ->> 'roundNumber' AS INT) AS round_number,
    try_cast(m ->> 'groupId' AS INT) AS group_id,
    try_cast(m ->> 'subphaseId' AS INT) AS subphase_id,
    try_cast(m ->> 'subphaseNumber' AS INT) AS subphase_number,
    try_cast(m ->> 'weekId' AS INT) AS week_id,
    try_cast(m ->> 'homeClubId' AS INT) AS home_club_id,
    try_cast(m ->> 'awayClubId' AS INT) AS away_club_id,
    try_cast(m -> 'homeTeam' ->> 'id' AS INT) AS home_team_id,
    try_cast(m -> 'awayTeam' ->> 'id' AS INT) AS away_team_id,
    try_cast(m ->> 'homeCurrentWins' AS INT) AS home_current_wins,
    try_cast(m ->> 'homeCurrentLosses' AS INT) AS home_current_losses,
    try_cast(m ->> 'awayCurrentWins' AS INT) AS away_current_wins,
    try_cast(m ->> 'awayCurrentLosses' AS INT) AS away_current_losses,
    m ->> 'serieData' AS playoff_serie_data,
    -- datos del partido que ya trae el calendario: sirven para los partidos aún sin cabecera
    m ->> 'matchStatus' AS match_status,
    try_cast(replace(m ->> 'startDateTime', 'Z', '') AS TIMESTAMP) AS match_start_time,
    try_cast(m ->> 'homeScore' AS INT) AS home_score,
    try_cast(m ->> 'awayScore' AS INT) AS away_score,
    m -> 'homeTeam' ->> 'fullName' AS home_team_full_name,
    m -> 'awayTeam' ->> 'fullName' AS away_team_full_name,
    m -> 'homeTeam' ->> 'abbreviatedName' AS home_team_abbr,
    m -> 'awayTeam' ->> 'abbreviatedName' AS away_team_abbr,
    m -> 'homeTeam' ->> 'logo' AS home_team_logo,
    m -> 'awayTeam' ->> 'logo' AS away_team_logo,
    current_timestamp AS cat_insert_date
FROM flattened
