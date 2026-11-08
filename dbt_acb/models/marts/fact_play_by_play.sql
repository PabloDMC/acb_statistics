{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Una fila por evento del play-by-play, ya con equipo fiable, posesión, tramo de quintetos y
-- situación de partido. Para saber quién estaba en pista, cruzar (match_id, stint_id, team_id)
-- con fact_lineups.

SELECT
    p.id,
    p.edition_id,
    p.competition_id,
    p.competition_phase,
    p.match_id,
    p.event_idx,
    p.event_order,

    p.quarter,
    p.minute,
    p.second,
    p.seconds_remaining,

    p.play_type_id,
    pt.play_name,
    pt.category AS play_category,
    pt.sub_category AS play_sub_category,
    p.play_tag,

    p.player_id,
    p.team_id,
    p.club_id,
    CASE WHEN p.team_id = p.home_team_id THEN p.away_team_id ELSE p.home_team_id END AS opponent_team_id,
    (p.team_id = p.home_team_id) AS is_home,

    p.points,
    CASE WHEN p.team_id = p.home_team_id THEN p.score_home ELSE p.score_away END AS score_team,
    CASE WHEN p.team_id = p.home_team_id THEN p.score_away ELSE p.score_home END AS score_opp,
    CASE WHEN p.team_id = p.home_team_id THEN p.score_home_before ELSE p.score_away_before END AS score_team_before,
    CASE WHEN p.team_id = p.home_team_id THEN p.score_away_before ELSE p.score_home_before END AS score_opp_before,
    p.score_home,
    p.score_away,

    p.is_clutch,
    p.is_assisted,
    p.is_and_one,

    e.offense_team_id,
    (p.team_id = e.offense_team_id) AS is_offense,
    e.possession_seq AS possession_id,
    e.stint_seq AS stint_id,
    e.event_kind,
    p.is_synthetic,

    p.cat_insert_date

FROM {{ ref('int_play_by_play') }} p
LEFT JOIN {{ ref('int_pbp_enriched') }} e
    USING (match_id, event_idx)
LEFT JOIN {{ ref('play_types') }} pt
    USING (play_type_id)
