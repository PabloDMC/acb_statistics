{{ config(
    materialized='view',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH base AS (

    SELECT *,
    100.0 / NULLIF(possessions, 0) AS factor
    FROM {{ ref('agg_player_totals') }}

)

SELECT
    edition_id,
    competition_id,
    competition_phase,
    player_id,
    team_id,
    player_game_role,
    games,
    games_started,
    seconds / 60.0 AS minutes,
    points * factor AS points_100poss,
    free_throws_made * factor AS free_throws_made_100poss,
    free_throws_attempted * factor AS free_throws_attempted_100poss,
    free_throws_made / NULLIF(free_throws_attempted, 0) AS free_throws_pct,
    two_pointers_made * factor AS two_pointers_made_100poss,
    two_pointers_attempted * factor AS two_pointers_attemped_100poss,
	two_pointers_made / NULLIF(two_pointers_attempted, 0) AS two_pointers_pct,
    three_pointers_made * factor AS three_pointers_made_100poss,
    three_pointers_attempted * factor AS three_pointers_attemped_100poss,
    three_pointers_made / NULLIF(three_pointers_attempted, 0) AS three_pointers_pct,
    field_goals_made * factor AS field_goals_made_100poss,
    field_goals_attempted * factor AS field_goals_attempted_100poss,    
    (two_pointers_made + three_pointers_made) / NULLIF(two_pointers_attempted + three_pointers_attempted, 0) AS field_goals_pct,
	(two_pointers_made + 1.5 * three_pointers_made) / NULLIF(two_pointers_attempted + three_pointers_attempted, 0) AS effective_field_goals_pct,
	points / NULLIF(2 * (two_pointers_attempted + three_pointers_attempted + 0.44 * free_throws_attempted), 0) AS true_shooting_pct,
    dunks * factor AS dunks_100poss,
    assists * factor AS assists_100poss,
    off_rebounds * factor AS off_rebounds_100poss,
    def_rebounds * factor AS def_rebounds_100poss,
    total_rebounds * factor AS total_rebounds_100poss,
    steals * factor AS steals_100poss,
    turnovers * factor AS turnovers_100poss,
    blocks * factor AS blocks_100poss,
    received_blocks * factor AS received_blocks_100poss,
    personal_fouls * factor AS personal_fouls_100poss,
    fouls_drawn * factor AS fouls_drawn_100poss,
    plus_minus * factor AS plus_minus_100poss,
    rating * factor AS rating_100poss,
    offensive_rating,
    defensive_rating,
    net_rating
FROM base