{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH poss AS (

    SELECT
        match_id,
        team_id,
        COUNT(*) AS offensive_possessions
    FROM {{ ref('fact_possessions') }}
    GROUP BY
        match_id,
        team_id

),

lineup_stats AS (

    SELECT

        p1.match_id,
        p1.team_id,

        p1.offensive_possessions,
        p2.offensive_possessions AS defensive_possessions,
        p1.offensive_possessions + p2.offensive_possessions AS possessions

    FROM poss p1
    LEFT JOIN poss p2
        ON p1.match_id = p2.match_id
       AND p1.team_id <> p2.team_id

),

matches AS (

    SELECT *
    FROM {{ ref('int_matches') }}

),

teams AS (

    SELECT

        edition_id,
        competition_id,
        round_type        AS competition_phase,
        match_id,

        home_team_id      AS team_id,
        home_team_club_id AS club_id,

        away_team_id      AS opponent_team_id,
        away_team_club_id AS opponent_club_id,

        TRUE              AS is_home,

        current_home_score AS points,
        current_away_score AS opponent_points

    FROM matches

    UNION ALL

    SELECT

        edition_id,
        competition_id,
        round_type,
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

-- Totales oficiales del equipo (bloque `total` del boxscore): incluyen los rebotes y pérdidas
-- "de equipo", que no pertenecen a ningún jugador y se perdían al sumar jugadores.
boxscore AS (

    SELECT *
    FROM {{ ref('int_team_boxscore') }}

),

-- los segundos jugados solo existen por jugador
playing_time AS (

    SELECT
        match_id,
        team_id,
        SUM(CAST(SPLIT_PART(play_time, ':', 1) AS BIGINT) * 60 + CAST(SPLIT_PART(play_time, ':', 2) AS BIGINT)) AS seconds
    FROM {{ ref('int_boxscore') }}
    GROUP BY match_id, team_id

),

names AS (

    SELECT team_id, full_name AS team_name, club_name
    FROM {{ ref('dim_teams') }}

)

SELECT

    t.*,
    n.team_name,
    n.club_name,
    opp.team_name AS opponent_team_name,
    (t.points > t.opponent_points) AS is_win,

    pt.seconds,
    bs.free_throws_made,
    bs.free_throws_attempted,
    bs.free_throws_made / NULLIF(bs.free_throws_attempted,0) AS free_throws_pct,
    bs.two_pointers_made,
    bs.two_pointers_attempted,
    bs.two_pointers_made / NULLIF(bs.two_pointers_attempted,0) AS two_pointers_pct,
    bs.three_pointers_made,
    bs.three_pointers_attempted,
    bs.three_pointers_made / NULLIF(bs.three_pointers_attempted,0) AS three_pointers_pct,
    bs.two_pointers_made + bs.three_pointers_made as field_goals_made,
    bs.two_pointers_attempted + bs.three_pointers_attempted as field_goals_attempted,
    (bs.two_pointers_made + bs.three_pointers_made) / NULLIF(bs.two_pointers_attempted + bs.three_pointers_attempted,0) AS field_goals_pct,
    (bs.two_pointers_made + 1.5 * bs.three_pointers_made) / NULLIF(bs.two_pointers_attempted + bs.three_pointers_attempted, 0) AS effective_field_goals_pct,
    t.points / NULLIF(2 * (bs.two_pointers_attempted + bs.three_pointers_attempted + 0.44 * bs.free_throws_attempted), 0) AS true_shooting_pct,
    bs.dunks,
    bs.assists,
    bs.off_rebounds,
    bs.def_rebounds,
    bs.total_rebounds,
    bs.steals,
    bs.turnovers,
    bs.blocks,
    bs.received_blocks,
    bs.personal_fouls,
    bs.fouls_drawn,

    bs.team_off_rebounds,
    bs.team_def_rebounds,
    bs.team_turnovers,
    bs.rating,
    (ls.offensive_possessions IS NOT NULL) AS has_possessions,
    ls.offensive_possessions,
    ls.defensive_possessions,
    ls.possessions,
    100.0 * t.points / NULLIF(ls.offensive_possessions,0) AS offensive_rating,
    100.0 * t.opponent_points / NULLIF(ls.defensive_possessions,0) AS defensive_rating,
    100.0 * t.points / NULLIF(ls.offensive_possessions,0)
    -
    100.0 * t.opponent_points / NULLIF(ls.defensive_possessions,0) AS net_rating

FROM teams t

LEFT JOIN boxscore bs
USING (
    match_id,
    team_id
)

LEFT JOIN playing_time pt
USING (
    match_id,
    team_id
)

LEFT JOIN lineup_stats ls
USING(
    match_id,
    team_id
)

LEFT JOIN names n
    ON n.team_id = t.team_id

LEFT JOIN names opp
    ON opp.team_id = t.opponent_team_id
