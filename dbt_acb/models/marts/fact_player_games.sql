{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH lineup_stats AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,

        match_id,

        team_id,

        UNNEST(player_ids) AS player_id,

        offensive_possessions,
        defensive_possessions,
        total_possessions AS possessions,

        team_points AS lineup_team_points,
        opp_points  AS lineup_opp_points

    FROM {{ ref('fact_lineups') }}

),

agg AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,

        match_id,

        team_id,
        player_id,

        SUM(offensive_possessions) AS offensive_possessions,
        SUM(defensive_possessions) AS defensive_possessions,
        SUM(possessions) AS possessions,

        SUM(lineup_team_points) AS lineup_team_points,

        SUM(lineup_opp_points) AS lineup_opp_points

    FROM lineup_stats

    GROUP BY ALL

),

team_totals AS (

    SELECT

        edition_id,
        competition_id,
        competition_phase,
        match_id,
        team_id,
        SUM(offensive_possessions) AS team_offensive_possessions,
        SUM(defensive_possessions) AS team_defensive_possessions,
        SUM(total_possessions) AS team_possessions,
        SUM(team_points) AS team_points,
        SUM(opp_points)  AS opp_points

    FROM {{ ref('fact_lineups') }}
    GROUP BY ALL

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

final AS (

    SELECT

        bs.id,
        bs.edition_id,
        bs.competition_id,
        bs.competition_phase,
        bs.match_id,
        bs.player_id,
        bs.team_id,
        bs.club_id,

        CASE
            WHEN bs.team_id = m.home_team_id THEN TRUE
            ELSE FALSE
        END AS is_home,

        CASE
            WHEN bs.team_id = m.home_team_id
                THEN m.away_team_id
            ELSE m.home_team_id
        END AS opponent_team_id,

        CASE
            WHEN bs.team_id = m.home_team_id
                THEN m.away_team_club_id
            ELSE m.home_team_club_id
        END AS opponent_club_id,

        CASE
            WHEN bs.team_id = m.home_team_id
                THEN m.home_score
            ELSE m.away_score
        END AS team_points,

        CASE
            WHEN bs.team_id = m.home_team_id
                THEN m.away_score
            ELSE m.home_score
        END AS opponent_points,

        CASE
            WHEN
                (
                    CASE
                        WHEN bs.team_id = m.home_team_id THEN m.home_score
                        ELSE m.away_score
                    END
                )
                >
                (
                    CASE
                        WHEN bs.team_id = m.home_team_id THEN m.away_score
                        ELSE m.home_score
                    END
                )
            THEN TRUE
            ELSE FALSE
        END AS is_win,
        bs.player_game_role,
        bs.is_starter,
        bs.play_time,
        (CAST(SPLIT_PART(bs.play_time, ':', 1) AS BIGINT) * 60 + CAST(SPLIT_PART(bs.play_time, ':', 2) AS BIGINT)) AS seconds,
        bs.points,
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
        bs.points / NULLIF(2 * (bs.two_pointers_attempted + bs.three_pointers_attempted + 0.44 * bs.free_throws_attempted), 0) AS true_shooting_pct,
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
        bs.plus_minus,
        bs.rating,

        (
            CASE WHEN bs.points >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN bs.total_rebounds >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN bs.assists >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN bs.steals >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN bs.blocks >= 10 THEN 1 ELSE 0 END
        ) AS double_double_categories,

        (
            (
                CASE WHEN bs.points >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.total_rebounds >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.assists >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.steals >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.blocks >= 10 THEN 1 ELSE 0 END
            ) >= 2
        ) AS is_double_double,

        (
            (
                CASE WHEN bs.points >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.total_rebounds >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.assists >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.steals >= 10 THEN 1 ELSE 0 END
                +
                CASE WHEN bs.blocks >= 10 THEN 1 ELSE 0 END
            ) >= 3
        ) AS is_triple_double,

        -- =========================
        -- ON COURT
        -- =========================

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

        bs.cat_insert_date

    FROM bs
    LEFT JOIN matches m
        USING(match_id)
    LEFT JOIN agg a
        USING(
            edition_id,
            competition_id,
            competition_phase,
            match_id,
            team_id,
            player_id
        )
    LEFT JOIN team_totals tt
        USING(
            edition_id,
            competition_id,
            competition_phase,
            match_id,
            team_id
        )

)

SELECT *
FROM final