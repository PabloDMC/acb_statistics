{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics'],
    cluster_by=['edition_id','competition_id','match_id','player_id']
) }}

WITH bs AS (

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
        current_home_score as home_score,
        current_away_score as away_score
    FROM {{ ref('int_matches') }}

),

final AS (

    SELECT

        bs.id,

        bs.edition_id,
        bs.competition_id,
        bs.match_id,

        bs.player_id,

        bs.team_id,
        bs.club_id,

        CASE
            WHEN bs.team_id = m.home_team_id THEN TRUE
            ELSE FALSE
        END AS is_home,

        CASE
            WHEN bs.team_id = m.home_team_id THEN m.away_team_id
            ELSE m.home_team_id
        END AS opponent_team_id,

        CASE
            WHEN bs.team_id = m.home_team_id THEN m.away_team_club_id
            ELSE m.home_team_club_id
        END AS opponent_club_id,

        CASE
            WHEN bs.team_id = m.home_team_id THEN m.home_score
            ELSE m.away_score
        END AS team_points,

        CASE
            WHEN bs.team_id = m.home_team_id THEN m.away_score
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

        bs.points,

        bs.free_throws_made,
        bs.free_throws_attempted,

        bs.two_pointers_made,
        bs.two_pointers_attempted,

        bs.three_pointers_made,
        bs.three_pointers_attempted,

        bs.two_pointers_made + bs.three_pointers_made AS field_goals_made,

        bs.two_pointers_attempted + bs.three_pointers_attempted AS field_goals_attempted,

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

        (bs.two_pointers_made + bs.three_pointers_made) / NULLIF(bs.two_pointers_attempted + bs.three_pointers_attempted, 0) AS fg_pct,
        bs.two_pointers_made / NULLIF(bs.two_pointers_attempted, 0) AS fg2_pct,
        bs.three_pointers_made / NULLIF(bs.three_pointers_attempted, 0) AS fg3_pct,
        bs.free_throws_made / NULLIF(bs.free_throws_attempted, 0) AS ft_pct,

        (
            bs.two_pointers_made
            + 1.5 * bs.three_pointers_made
        )
        /
        NULLIF(
            bs.two_pointers_attempted
            + bs.three_pointers_attempted,
            0
        ) AS effective_fg_pct,

        bs.points
        /
        NULLIF(
            2 * (
                bs.two_pointers_attempted
                + bs.three_pointers_attempted
                + 0.44 * bs.free_throws_attempted
            ),
            0
        ) AS true_shooting_pct,

        (
            CASE WHEN points >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN total_rebounds >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN assists >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN steals >= 10 THEN 1 ELSE 0 END
            +
            CASE WHEN blocks >= 10 THEN 1 ELSE 0 END
        ) AS double_double_categories,

        CASE
            WHEN
                (
                    CASE WHEN points >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN total_rebounds >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN assists >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN steals >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN blocks >= 10 THEN 1 ELSE 0 END
                ) >= 2
            THEN TRUE
            ELSE FALSE
        END AS is_double_double,

        CASE
            WHEN
                (
                    CASE WHEN points >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN total_rebounds >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN assists >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN steals >= 10 THEN 1 ELSE 0 END
                    +
                    CASE WHEN blocks >= 10 THEN 1 ELSE 0 END
                ) >= 3
            THEN TRUE
            ELSE FALSE
        END AS is_triple_double,

        bs.cat_insert_date

    FROM bs
    LEFT JOIN matches m USING(match_id)

)

SELECT *
FROM final