{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Una fila por jugador, equipo y fase de una competición en una temporada.
-- El rol (player_game_role) es un atributo del jugador, no parte del grano: si cambiara a media
-- temporada partiría sus totales en dos filas. Se guarda el más frecuente.

with agg as (

	select

		edition_id,
		competition_id,
		competition_phase,
		player_id,
		team_id,

		any_value(player_name) as player_name,
		any_value(team_name) as team_name,
		any_value(club_id) as club_id,
		any_value(club_name) as club_name,
		mode(player_game_role) as player_game_role,

		-- PJ oficial: solo partidos con minutos. Los convocados que no salen (0:00) aparecen en el
		-- boxscore y antes contaban como partido jugado, inflando el denominador de las medias.
		count(*) filter (where seconds > 0) as games,
		count(*) filter (where seconds > 0 and has_possessions) as games_with_possessions,
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

		-- con el jugador en pista
        sum(offensive_possessions) as offensive_possessions,
        sum(defensive_possessions) as defensive_possessions,
        sum(possessions) as possessions,
        sum(lineup_team_points) as team_points,
        sum(lineup_opp_points) as opp_points,

		-- con el jugador en el banquillo (solo partidos en los que participó)
		sum(off_offensive_possessions) as off_offensive_possessions,
		sum(off_defensive_possessions) as off_defensive_possessions,
		sum(off_team_points) as off_team_points,
		sum(off_opp_points) as off_opp_points

	from {{ ref('fact_player_games') }}

	group by edition_id, competition_id, competition_phase, player_id, team_id

)

select 

	edition_id,
    competition_id,
    competition_phase,
    player_id,
    player_name,
    team_id,
    team_name,
    club_id,
    club_name,
    player_game_role,
	games,
	games_with_possessions,
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

	off_offensive_possessions,
	off_defensive_possessions,
	off_team_points,
	off_opp_points,

    100.0 * team_points / NULLIF(offensive_possessions, 0) as offensive_rating,
    100.0 * opp_points / NULLIF(defensive_possessions, 0) as defensive_rating,
    100.0 * team_points / NULLIF(offensive_possessions, 0)
    - 100.0 * opp_points / NULLIF(defensive_possessions, 0) as net_rating,

    100.0 * off_team_points / NULLIF(off_offensive_possessions, 0) as off_offensive_rating,
    100.0 * off_opp_points / NULLIF(off_defensive_possessions, 0) as off_defensive_rating,
    100.0 * off_team_points / NULLIF(off_offensive_possessions, 0)
    - 100.0 * off_opp_points / NULLIF(off_defensive_possessions, 0) as off_net_rating,

	-- on/off = rating con el jugador en pista menos rating sin él. Las columnas off_* ya son
	-- "sin él": antes se les volvía a restar lo jugado en pista y el resultado no tenía sentido.
    (
		100.0 * team_points / NULLIF(offensive_possessions, 0)
		- 100.0 * off_team_points / NULLIF(off_offensive_possessions, 0)
	) AS onoff_offensive_rating,

	(
		100.0 * opp_points / NULLIF(defensive_possessions, 0)
		- 100.0 * off_opp_points / NULLIF(off_defensive_possessions, 0)
	) AS onoff_defensive_rating,

	(
		100.0 * team_points / NULLIF(offensive_possessions, 0)
		- 100.0 * opp_points / NULLIF(defensive_possessions, 0)
	)
	-
	(
		100.0 * off_team_points / NULLIF(off_offensive_possessions, 0)
		- 100.0 * off_opp_points / NULLIF(off_defensive_possessions, 0)
	) AS onoff_net_rating

from agg
