{{ config(
  materialized='table',
  schema='intermediate',
  tags=['acb_analytics'],
  cluster_by=['edition_id','match_id']
) }}

WITH feed AS (
  SELECT *
  FROM {{ ref('stg_apiacb__play_by_play') }}
),

-- Algunos partidos llegan sin los eventos de quinteto inicial (599). Sin ellos no se puede
-- reconstruir quién está en pista, así que se generan a partir de los titulares del boxscore.
missing_starters AS (
  SELECT
    b.edition_id,
    b.match_id,
    b.player_id
  FROM {{ ref('stg_apiacb__boxscore') }} b
  WHERE b.quarter = 0
    AND b.is_starter
    AND b.match_id IN (SELECT match_id FROM feed)
    AND b.match_id NOT IN (SELECT match_id FROM feed WHERE play_type = 599 AND match_id IS NOT NULL)
),

pbp AS (
  SELECT
    edition_id,
    match_id,
    play_idx,
    play_order,
    player_license_id,
    play_type,
    play_tag,
    quarter,
    minute,
    second,
    is_local_action,
    score_home,
    score_away,
    cat_insert_date,
    FALSE AS is_synthetic
  FROM feed

  UNION ALL

  SELECT
    edition_id,
    match_id,
    ROW_NUMBER() OVER (PARTITION BY match_id ORDER BY player_id) AS play_idx,
    -1 AS play_order,            -- antes que cualquier evento real
    player_id AS player_license_id,
    599 AS play_type,
    NULL AS play_tag,
    1 AS quarter,
    10 AS minute,
    0 AS second,
    NULL AS is_local_action,     -- el equipo sale del boxscore
    0 AS score_home,
    0 AS score_away,
    current_timestamp AS cat_insert_date,
    TRUE AS is_synthetic
  FROM missing_starters
),

match_meta AS (
  SELECT
    mh.match_id,
    mh.competition_id,
    ml.round_type as competition_phase,
    mh.home_team_id,
    mh.away_team_id,
    mh.home_team_club_id,
    mh.away_team_club_id
    FROM {{ ref('stg_apiacb__matchlist') }} ml
    JOIN {{ ref('stg_apiacb__match_header') }} mh USING (match_id)
),

-- Equipo de cada jugador en cada partido según el boxscore.
roster AS (
  SELECT
    match_id,
    player_id,
    any_value(team_id) AS team_id
  FROM {{ ref('stg_apiacb__boxscore') }}
  WHERE quarter = 0
    AND player_id IS NOT NULL
  GROUP BY match_id, player_id
),

resolved AS (
  SELECT
    e.edition_id,
    e.match_id,
    mm.competition_id,
    mm.competition_phase,
    e.play_order AS event_order,
    -- Orden real del partido: `order` no es único, se desempata con la posición en el array.
    -- El cuarto va primero porque el feed a veces añade al final una corrección de un cuarto
    -- ya terminado (4 partidos en el histórico): así cae al final de SU cuarto y los cuartos
    -- quedan siempre contiguos, que es lo que asume int_pbp_enriched.
    ROW_NUMBER() OVER (
      PARTITION BY e.match_id
      ORDER BY e.quarter, e.play_order, e.play_idx
    ) AS event_idx,
    e.player_license_id,
    e.play_type AS play_type_id,
    e.play_tag,
    e.quarter,
    e.minute,
    e.second,
    ((e.minute * 60) + e.second) AS seconds_remaining,
    mm.home_team_id,
    mm.away_team_id,
    mm.home_team_club_id,
    mm.away_team_club_id,
    CASE WHEN e.is_local_action THEN mm.home_team_id ELSE mm.away_team_id END AS local_flag_team_id,
    -- El flag `local` del PBP falla en muchos partidos de temporadas antiguas: cuando el evento
    -- tiene jugador, su equipo es el del boxscore; `local` queda para los eventos de equipo.
    coalesce(
      r.team_id,
      CASE WHEN e.is_local_action THEN mm.home_team_id ELSE mm.away_team_id END
    ) AS team_id,
    e.score_home,
    e.score_away,
    CASE e.play_type
      WHEN 92 THEN 1
      WHEN 93 THEN 2
      WHEN 100 THEN 2
      WHEN 94 THEN 3
      ELSE 0
    END AS points,
    e.is_synthetic,
    e.cat_insert_date
  FROM pbp e
  LEFT JOIN match_meta mm USING (match_id)
  LEFT JOIN roster r
    ON r.match_id = e.match_id
   AND r.player_id = e.player_license_id
),

scored AS (
  SELECT
    *,
    CASE WHEN team_id = home_team_id THEN home_team_club_id ELSE away_team_club_id END AS club_id,
    -- El marcador del feed es el de DESPUÉS del evento; para situaciones de partido (clutch)
    -- interesa el de antes de la jugada.
    score_home - CASE WHEN team_id = home_team_id THEN points ELSE 0 END AS score_home_before,
    score_away - CASE WHEN team_id = away_team_id THEN points ELSE 0 END AS score_away_before
  FROM resolved
),

flagged AS (
  SELECT
    *,
    LEAD(play_type_id) OVER w AS next_play_type_id,
    LEAD(team_id) OVER w AS next_team_id,
    -- siguiente evento de balón vivo y siguiente falta personal de 1 tiro, para detectar 2+1
    MIN(CASE WHEN play_type_id IN (92, 93, 94, 96, 97, 98, 100, 101, 104, 106, 533) THEN event_idx END)
      OVER (PARTITION BY match_id, quarter ORDER BY event_idx ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING)
      AS next_live_event_idx,
    MIN(CASE WHEN play_type_id = 160 THEN event_idx END)
      OVER (PARTITION BY match_id, quarter ORDER BY event_idx ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING)
      AS next_one_shot_foul_idx
  FROM scored
  WINDOW w AS (PARTITION BY match_id ORDER BY event_idx)
)

SELECT
  concat_ws('_', match_id, event_idx) AS id,
  edition_id,
  competition_id,
  competition_phase,
  match_id,
  event_idx,
  event_order,
  quarter,
  minute,
  second,
  seconds_remaining,
  play_type_id,
  play_tag,
  player_license_id AS player_id,
  team_id,
  club_id,
  home_team_id,
  away_team_id,
  (NOT is_synthetic AND team_id <> local_flag_team_id) AS is_local_flag_wrong,
  is_synthetic,
  points,
  score_home,
  score_away,
  (score_home - score_away) AS score_margin,
  score_home_before,
  score_away_before,
  (
    (quarter = 4 AND seconds_remaining <= 300) OR quarter > 4
  ) AND abs(score_home_before - score_away_before) <= 5 AS is_clutch,
  (
    play_type_id IN (93, 94, 100)
    AND next_play_type_id IN (107, 108)
    AND next_team_id = team_id
  ) AS is_assisted,
  (
    play_type_id IN (93, 94, 100)
    AND next_one_shot_foul_idx IS NOT NULL
    AND (next_live_event_idx IS NULL OR next_one_shot_foul_idx < next_live_event_idx)
  ) AS is_and_one,
  cat_insert_date
FROM flagged
