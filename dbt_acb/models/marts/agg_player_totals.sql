{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

with agg as (
	select
		edition_id,
		competition_id,
		competition_phase,
		player_id,
		team_id,
		player_game_role,
		count(1) as games,
		sum(is_starter) as games_started,
		sum(seconds) as seconds,
		sum(points) as points,
		sum(free_throws_made) as free_throws_made,
		sum(free_throws_attempted) as free_throws_attempted,
		sum(two_pointers_made) as two_pointers_made,
		sum(two_pointers_attempted) as two_pointers_attempted,
		sum(three_pointers_made) as three_pointers_made,
		sum(three_pointers_attempted) as three_pointers_attempted,
		sum(field_goals_made) as field_goals_made,
		sum(field_goals_attempted) as field_goals_attempted,
		sum(dunks) as dunks,
		sum(assists) as assists,
		sum(off_rebounds) as off_rebounds,
		sum(def_rebounds) as def_rebounds,
		sum(total_rebounds) as total_rebounds,
		sum(steals) as steals,
		sum(turnovers) as turnovers,
		sum(blocks) as blocks,
		sum(received_blocks) as received_blocks,
		sum(personal_fouls) as personal_fouls,
		sum(fouls_drawn) as fouls_drawn,
		sum(plus_minus) as plus_minus,
		sum(rating) as rating,
		sum(is_double_double) as is_double_double,
		sum(is_triple_double) as is_triple_double,
        sum(offensive_possessions) as offensive_possessions,
        sum(defensive_possessions) as defensive_possessions,
        sum(possessions) as possessions,
        sum(lineup_team_points) as team_points,
        sum(lineup_opp_points) as opp_points,
		sum(off_offensive_possessions) as off_offensive_possessions,
		sum(off_defensive_possessions) as off_defensive_possessions,
		sum(off_team_points) as off_team_points,
		sum(off_opp_points) as off_opp_points
	from {{ ref('fact_player_games') }}
	group by edition_id, competition_id, competition_phase, player_id, team_id, player_game_role
)
select 
	edition_id,
    competition_id,
    competition_phase,
    player_id,
    team_id,
    player_game_role,
	games,
	games_started,
    seconds,
	points,
	free_throws_made,
	free_throws_attempted,
	free_throws_made / NULLIF(free_throws_attempted, 0) AS free_throws_pct,
	two_pointers_made,
	two_pointers_attempted,
	two_pointers_made / NULLIF(two_pointers_attempted, 0) AS two_pointers_pct,
	three_pointers_made,
	three_pointers_attempted,
	three_pointers_made / NULLIF(three_pointers_attempted, 0) AS three_pointers_pct,
	field_goals_made,
	field_goals_attempted,
	(two_pointers_made + three_pointers_made) / NULLIF(two_pointers_attempted + three_pointers_attempted, 0) AS field_goals_pct,
	(two_pointers_made + 1.5 * three_pointers_made) / NULLIF(two_pointers_attempted + three_pointers_attempted, 0) AS effective_field_goals_pct,
	points / NULLIF(2 * (two_pointers_attempted + three_pointers_attempted + 0.44 * free_throws_attempted), 0) AS true_shooting_pct,
	dunks,
	assists,
	off_rebounds,
	def_rebounds,
	total_rebounds,
	steals,
	turnovers,
	blocks,
	received_blocks,
	personal_fouls,
	fouls_drawn,
	plus_minus,
	rating,
	is_double_double,
	is_triple_double,
	offensive_possessions,
	defensive_possessions,
    possessions,
    team_points,
    opp_points,
    100.0 * team_points / NULLIF(offensive_possessions, 0) as offensive_rating,
    100.0 * opp_points / NULLIF(defensive_possessions, 0) as defensive_rating,
    100.0 * (team_points / NULLIF(offensive_possessions, 0) - opp_points / NULLIF(defensive_possessions, 0)) as net_rating,
    (
		(100.0 * team_points / NULLIF(offensive_possessions,0))
		-
		(100.0 * (off_team_points - team_points) / NULLIF(off_offensive_possessions - offensive_possessions,0))
	) AS onoff_offensive_rating,

	(
		(100.0 * opp_points / NULLIF(defensive_possessions,0))
		-
		(100.0 * (off_opp_points - opp_points) / NULLIF(off_defensive_possessions - defensive_possessions,0))
	) AS onoff_defensive_rating,

	(
		(100.0 * team_points / NULLIF(offensive_possessions,0))
		-
		(100.0 * opp_points / NULLIF(defensive_possessions,0))
	)
	-
	(
		(100.0 * (off_team_points - team_points) / NULLIF(off_offensive_possessions - offensive_possessions,0))
		-
		(100.0 * (off_opp_points - opp_points) / NULLIF(off_defensive_possessions - defensive_possessions,0))
	) AS onoff_net_rating

from agg