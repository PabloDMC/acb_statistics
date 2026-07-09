{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH matches AS (

    SELECT *
    FROM {{ ref('int_matches') }}

),

teams AS (

SELECT

    edition_id,
    competition_id,
    match_id,

    home_team_id      AS team_id,
    home_team_club_id AS club_id,

    away_team_id      AS opponent_team_id,
    away_team_club_id AS opponent_club_id,

    TRUE AS is_home,

    current_home_score AS points,
    current_away_score AS opponent_points

FROM matches

UNION ALL

SELECT

    edition_id,
    competition_id,
    match_id,

    away_team_id,
    away_team_club_id,

    home_team_id,
    home_team_club_id,

    FALSE,

    current_away_score,
    current_home_score

FROM matches

),

box AS (

SELECT

    edition_id,
    match_id,
    team_id,

    SUM(points)                     AS points,
    SUM(free_throws_made)           AS ftm,
    SUM(free_throws_attempted)      AS fta,

    SUM(two_pointers_made)          AS fg2m,
    SUM(two_pointers_attempted)     AS fg2a,

    SUM(three_pointers_made)        AS fg3m,
    SUM(three_pointers_attempted)   AS fg3a,

    SUM(assists)                    AS assists,

    SUM(off_rebounds)               AS off_rebounds,
    SUM(def_rebounds)               AS def_rebounds,
    SUM(total_rebounds)             AS rebounds,

    SUM(steals)                     AS steals,

    SUM(turnovers)                  AS turnovers,

    SUM(blocks)                     AS blocks,

    SUM(received_blocks)            AS received_blocks,

    SUM(personal_fouls)             AS personal_fouls,

    SUM(fouls_drawn)                AS fouls_drawn

FROM {{ ref('int_boxscore') }}

GROUP BY
    edition_id,
    match_id,
    team_id

)

SELECT

    t.*,

    b.ftm,
    b.fta,

    b.fg2m,
    b.fg2a,

    b.fg3m,
    b.fg3a,

    b.fg2m + b.fg3m AS fgm,
    b.fg2a + b.fg3a AS fga,

    b.assists,

    b.off_rebounds,
    b.def_rebounds,
    b.rebounds,

    b.steals,

    b.turnovers,

    b.blocks,

    b.received_blocks,

    b.personal_fouls,

    b.fouls_drawn,

    t.points - t.opponent_points AS margin,

    t.points > t.opponent_points AS is_win,


    (b.fg2m + b.fg3m) / NULLIF(b.fg2a + b.fg3a, 0) AS fg_pct,
    b.fg2m / NULLIF(b.fg2a, 0) AS fg2_pct,
    b.fg3m / NULLIF(b.fg3a, 0) AS fg3_pct,
    b.ftm / NULLIF(b.fta, 0) AS ft_pct,

    (
        b.fg2m + 1.5*b.fg3m
    )
    /
    NULLIF(
        b.fg2a + b.fg3a,
        0
    ) AS effective_fg_pct,

    t.points
    /
    NULLIF(
        2 * (
            b.fg2a
            + b.fg3a
            + 0.44*b.fta
        ),
        0
    ) AS true_shooting_pct

FROM teams t
LEFT JOIN box b
USING (
    edition_id,
    match_id,
    team_id
)