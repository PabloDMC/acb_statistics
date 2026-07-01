{{ config(
  materialized='table',
  schema='intermediate',
  tags=['acb_analytics'],
  cluster_by=['edition_id','match_id']
) }}

WITH pbp AS (
  SELECT *
  FROM {{ ref('stg_apiacb__play_by_play') }}
),

match_meta AS (
  SELECT
    match_id,
    home_team_id,
    away_team_id,
    home_team_club_id,
    away_team_club_id
  FROM {{ ref('stg_apiacb__match_header') }}
),

resolved AS (
  SELECT
    e.edition_id,
    e.match_id,
    e.play_order AS event_order,
    e.player_license_id,
    e.play_type AS play_type_id,
    e.play_tag,
    e.quarter,
    e.minute,
    e.second,
    ((e.minute * 60) + e.second) AS seconds_remaining,
    CASE WHEN e.is_local_action THEN mm.home_team_id ELSE mm.away_team_id END AS team_id,
    CASE WHEN e.is_local_action THEN mm.home_team_club_id ELSE mm.away_team_club_id END AS club_id,
    e.score_home,
    e.score_away,
    (e.score_home - e.score_away) AS score_margin,
    e.cat_insert_date
  FROM pbp e
  LEFT JOIN match_meta mm USING (match_id)
)

SELECT
  edition_id,
  match_id,
  event_order,
  quarter AS period,
  minute,
  second,
  seconds_remaining,
  play_type_id,
  play_tag,
  player_license_id AS player_id,
  team_id,
  club_id,
  score_home,
  score_away,
  score_margin,
  cat_insert_date
FROM resolved