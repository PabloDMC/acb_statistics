{{ config(
    materialized='view',
    schema='marts',
    tags=['acb_analytics']
) }}

WITH base AS (

    SELECT *,
    seconds / 2400.0 AS factor
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
    points / factor AS points_40min,
    free_throws_made / factor AS free_throws_made_40min,
    free_throws_attempted / factor AS free_throws_attempted_40min,
    free_throws_made / NULLIF(free_throws_attempted, 0) AS free_throws_pct,
    two_pointers_made / factor AS two_pointers_made_40min,
    two_pointers_attempted / factor AS two_pointers_attemped_40min,
	two_pointers_made / NULLIF(two_pointers_attempted, 0) AS two_pointers_pct,
    three_pointers_made / factor AS three_pointers_made_40min,
    three_pointers_attempted / factor AS three_pointers_attemped_40min,
    three_pointers_made / NULLIF(three_pointers_attempted, 0) AS three_pointers_pct,
    field_goals_made / factor AS field_goals_made_40min,
    field_goals_attempted / factor AS field_goals_attempted_40min,    
    (two_pointers_made + three_pointers_made) / NULLIF(two_pointers_attempted + three_pointers_attempted, 0) AS field_goals_pct,
	(two_pointers_made + 1.5 * three_pointers_made) / NULLIF(two_pointers_attempted + three_pointers_attempted, 0) AS effective_field_goals_pct,
	points / NULLIF(2 * (two_pointers_attempted + three_pointers_attempted + 0.44 * free_throws_attempted), 0) AS true_shooting_pct,
    dunks / factor AS dunks_40min,
    assists / factor AS assists_40min,
    off_rebounds / factor AS off_rebounds_40min,
    def_rebounds / factor AS def_rebounds_40min,
    total_rebounds / factor AS total_rebounds_40min,
    steals / factor AS steals_40min,
    turnovers / factor AS turnovers_40min,
    blocks / factor AS blocks_40min,
    received_blocks / factor AS received_blocks_40min,
    personal_fouls / factor AS personal_fouls_40min,
    fouls_drawn / factor AS fouls_drawn_40min,
    plus_minus / factor AS plus_minus_40min,
    rating / factor AS rating_40min
FROM base