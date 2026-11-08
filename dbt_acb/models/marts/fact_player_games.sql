{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Una fila por jugador y partido: boxscore + lo que hizo su equipo con él en pista (on) y sin
-- él (off), a partir de los tramos de fact_lineups.

WITH lineups AS (

    SELECT *
    FROM {{ ref('fact_lineups') }}

),

on_court AS (

    SELECT
        match_id,
        team_id,
        player_id,
        SUM(offensive_possessions) AS offensive_possessions,
        SUM(defensive_possessions) AS defensive_possessions,
        SUM(total_possessions) AS possessions,
        SUM(team_points) AS lineup_team_points,
        SUM(opp_points) AS lineup_opp_points
    FROM (
        SELECT
            match_id,
            team_id,
            UNNEST(player_ids) AS player_id,
            offensive_possessions,
            defensive_possessions,
            total_possessions,
            team_points,
            opp_points
        FROM lineups
    )
    GROUP BY match_id, team_id, player_id

),

team_totals AS (

    SELECT
        match_id,
        team_id,
        SUM(offensive_possessions) AS team_offensive_possessions,
        SUM(defensive_possessions) AS team_defensive_possessions,
        SUM(total_possessions) AS team_possessions,
        SUM(team_points) AS team_points,
        SUM(opp_points) AS opp_points
    FROM lineups
    GROUP BY match_id, team_id

),

bs AS (

    SELECT *
    FROM {{ ref('int_boxscore') }}

),

matches AS (

    SELECT
        match_id,
        home_team_id,
        away_team_id,
        home_team_club_id,
        away_team_club_id,
        current_home_score AS home_score,
        current_away_score AS away_score
    FROM {{ ref('int_matches') }}

),

team_names AS (

    SELECT team_id, full_name AS team_name, club_name
    FROM {{ ref('dim_teams') }}

),

base AS (

    SELECT
        bs.*,
        (bs.team_id = m.home_team_id) AS is_home,
        CASE WHEN bs.team_id = m.home_team_id THEN m.away_team_id ELSE m.home_team_id END AS opponent_team_id,
        CASE WHEN bs.team_id = m.home_team_id THEN m.away_team_club_id ELSE m.home_team_club_id END AS opponent_club_id,
        CASE WHEN bs.team_id = m.home_team_id THEN m.home_score ELSE m.away_score END AS team_points,
        CASE WHEN bs.team_id = m.home_team_id THEN m.away_score ELSE m.home_score END AS opponent_points,
        (
            CASE WHEN bs.points >= 10 THEN 1 ELSE 0 END
            + CASE WHEN bs.total_rebounds >= 10 THEN 1 ELSE 0 END
            + CASE WHEN bs.assists >= 10 THEN 1 ELSE 0 END
            + CASE WHEN bs.steals >= 10 THEN 1 ELSE 0 END
            + CASE WHEN bs.blocks >= 10 THEN 1 ELSE 0 END
        ) AS double_double_categories
    FROM bs
    LEFT JOIN matches m
        USING (match_id)

),

final AS (

    SELECT

        b.id,

        b.edition_id,
        b.competition_id,
        b.competition_phase,

        b.match_id,

        b.player_id,
        pl.player_name,

        b.team_id,
        tn.team_name,
        b.club_id,
        tn.club_name,

        b.is_home,
        b.opponent_team_id,
        opp.team_name AS opponent_team_name,
        b.opponent_club_id,

        b.team_points,
        b.opponent_points,
        coalesce(b.team_points > b.opponent_points, FALSE) AS is_win,

        b.player_game_role,
        b.is_starter,
        b.play_time,
        (CAST(SPLIT_PART(b.play_time, ':', 1) AS BIGINT) * 60 + CAST(SPLIT_PART(b.play_time, ':', 2) AS BIGINT)) AS seconds,

        b.points,

        b.free_throws_made,
        b.free_throws_attempted,
        b.free_throws_made / NULLIF(b.free_throws_attempted,0) AS free_throws_pct,

        b.two_pointers_made,
        b.two_pointers_attempted,
        b.two_pointers_made / NULLIF(b.two_pointers_attempted,0) AS two_pointers_pct,

        b.three_pointers_made,
        b.three_pointers_attempted,
        b.three_pointers_made / NULLIF(b.three_pointers_attempted,0) AS three_pointers_pct,

        b.two_pointers_made + b.three_pointers_made AS field_goals_made,
        b.two_pointers_attempted + b.three_pointers_attempted AS field_goals_attempted,
        (b.two_pointers_made + b.three_pointers_made) / NULLIF(b.two_pointers_attempted + b.three_pointers_attempted,0) AS field_goals_pct,
        (b.two_pointers_made + 1.5 * b.three_pointers_made) / NULLIF(b.two_pointers_attempted + b.three_pointers_attempted, 0) AS effective_field_goals_pct,
        b.points / NULLIF(2 * (b.two_pointers_attempted + b.three_pointers_attempted + 0.44 * b.free_throws_attempted), 0) AS true_shooting_pct,

        b.dunks,
        b.assists,
        b.off_rebounds,
        b.def_rebounds,
        b.total_rebounds,
        b.steals,
        b.turnovers,
        b.blocks,
        b.received_blocks,
        b.personal_fouls,
        b.fouls_drawn,
        b.plus_minus,
        b.rating,

        b.double_double_categories,
        (b.double_double_categories >= 2) AS is_double_double,
        (b.double_double_categories >= 3) AS is_triple_double,

        -- =========================
        -- ON COURT
        -- =========================

        -- el partido tiene play-by-play (y por tanto posesiones) para este equipo
        (tt.team_offensive_possessions IS NOT NULL) AS has_possessions,
        a.offensive_possessions,
        a.defensive_possessions,
        a.possessions,

        a.lineup_team_points,
        a.lineup_opp_points,

        100.0 * a.lineup_team_points / NULLIF(a.offensive_possessions,0) AS offensive_rating,
        100.0 * a.lineup_opp_points / NULLIF(a.defensive_possessions,0) AS defensive_rating,

        100.0 * a.lineup_team_points / NULLIF(a.offensive_possessions,0)
        -
        100.0 * a.lineup_opp_points  / NULLIF(a.defensive_possessions,0) AS net_rating,

        -- =========================
        -- OFF COURT
        -- =========================

        tt.team_offensive_possessions - a.offensive_possessions AS off_offensive_possessions,
        tt.team_defensive_possessions - a.defensive_possessions AS off_defensive_possessions,
        tt.team_possessions - a.possessions AS off_possessions,

        tt.team_points - a.lineup_team_points  AS off_team_points,
        tt.opp_points - a.lineup_opp_points AS off_opp_points,

        -- =========================
        -- ON-OFF
        -- =========================

        (
            (100.0 * a.lineup_team_points / NULLIF(a.offensive_possessions,0))
            -
            (100.0 * (tt.team_points - a.lineup_team_points) / NULLIF(tt.team_offensive_possessions - a.offensive_possessions,0))
        ) AS onoff_offensive_rating,

        (
            (100.0 * a.lineup_opp_points / NULLIF(a.defensive_possessions,0))
            -
            (100.0 * (tt.opp_points - a.lineup_opp_points) / NULLIF(tt.team_defensive_possessions - a.defensive_possessions,0))
        ) AS onoff_defensive_rating,

        (
            (100.0 * a.lineup_team_points / NULLIF(a.offensive_possessions,0))
            -
            (100.0 * a.lineup_opp_points / NULLIF(a.defensive_possessions,0))
        )
        -
        (
            (100.0 * (tt.team_points - a.lineup_team_points) / NULLIF(tt.team_offensive_possessions - a.offensive_possessions,0))
            -
            (100.0 * (tt.opp_points - a.lineup_opp_points) / NULLIF(tt.team_defensive_possessions - a.defensive_possessions,0))
        ) AS onoff_net_rating,

        b.cat_insert_date

    FROM base b

    LEFT JOIN on_court a
        ON a.match_id = b.match_id
       AND a.team_id = b.team_id
       AND a.player_id = b.player_id

    LEFT JOIN team_totals tt
        ON tt.match_id = b.match_id
       AND tt.team_id = b.team_id

    LEFT JOIN {{ ref('dim_players') }} pl
        ON pl.player_id = b.player_id

    LEFT JOIN team_names tn
        ON tn.team_id = b.team_id

    LEFT JOIN team_names opp
        ON opp.team_id = b.opponent_team_id

)

SELECT *
FROM final
