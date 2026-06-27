{{ config(
    materialized='table',
    tags=["acb_statistics"],
    cluster_by=['edition_id', 'match_id']
) }}

WITH flattened_matches AS (
    SELECT
        CAST(editionId AS INT) AS edition_id,
        CAST(competitionId AS INT) AS competition_id,
        CAST(matchGrouping AS VARCHAR) AS match_grouping,
        unnest(matches) AS m
    FROM {{ source('acb_landing', 'matchlists') }}
)

SELECT
    edition_id,
    competition_id,
    match_grouping,
    CAST(m.id AS INT) AS match_id,
    CAST(m.roundType AS VARCHAR) AS round_type,
    CAST(m.roundId AS INT) AS round_id,
    CAST(m.roundNumber AS INT) AS round_number,
    CAST(m.groupId AS INT) AS group_id,
    CAST(m.subphaseId AS INT) AS subphase_id,
    CAST(m.subphaseNumber AS INT) AS subphase_number,
    CAST(m.weekId AS INT) AS week_id,
    CAST(m.homeClubId AS INT) AS home_club_id,
    CAST(m.awayClubId AS INT) AS away_club_id,
    CAST(m.homeTeam.id AS INT) AS home_team_id,
    CAST(m.awayTeam.id AS INT) AS away_team_id,
    CAST(m.homeCurrentWins AS INT) AS home_current_wins,
    CAST(m.homeCurrentLosses AS INT) AS home_current_losses,
    CAST(m.awayCurrentWins AS INT) AS away_current_wins,
    CAST(m.awayCurrentLosses AS INT) AS away_current_losses,
    CAST(m.serieData AS VARCHAR) AS playoff_serie_data
FROM flattened_matches