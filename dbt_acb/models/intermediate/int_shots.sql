{{ config(
    materialized='table',
    schema = "intermediate",
    tags=["acb_analytics"],
    cluster_by=['edition_id', 'match_id', 'player_id']
) }}

WITH shots AS (
    SELECT
        competition_id,
        edition_id,
        match_id,
        shot_id,
        player_license_id AS player_id,

        CASE WHEN edition_id < 85 THEN pos_x * 280 ELSE pos_x END AS norm_pos_x,
        CASE WHEN edition_id < 85 THEN pos_y * 150 - 7500 ELSE pos_y END AS norm_pos_y,

        try_cast(play_type AS INT) AS play_type,
        quarter,
        minute,
        second,
        is_local_team,
        score_home,
        score_away,

        cat_insert_date
    FROM {{ ref('stg_apiacb__match_shots') }}
),

-- Equipo de cada jugador en cada partido según el boxscore (el flag `local` falla en
-- temporadas antiguas, igual que en el play-by-play).
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

-- Evento del play-by-play que corresponde a cada lanzamiento. No hay clave común, así que se
-- empareja por partido, cuarto, reloj, jugador y tipo de jugada, y entre lanzamientos idénticos
-- en el mismo segundo (dos tiros libres) por orden de aparición.
pbp_shots AS (
    SELECT
        match_id,
        quarter,
        minute,
        second,
        player_id,
        play_type_id,
        event_idx,
        is_assisted,
        is_and_one,
        ROW_NUMBER() OVER (
            PARTITION BY match_id, quarter, minute, second, player_id, play_type_id
            ORDER BY event_idx
        ) AS occurrence
    FROM {{ ref('int_play_by_play') }}
    WHERE play_type_id IN (92, 93, 94, 96, 97, 98, 100, 533)
),

shots_numbered AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY match_id, quarter, minute, second, player_id, play_type
            ORDER BY try_cast(shot_id AS INT), shot_id
        ) AS occurrence
    FROM shots
),

mh AS (
  SELECT
    mh.match_id,
    ml.round_type as competition_phase,
    mh.home_team_id,
    mh.away_team_id,
    mh.home_team_club_id,
    mh.away_team_club_id
    FROM {{ ref('stg_apiacb__matchlist') }} ml
    JOIN {{ ref('stg_apiacb__match_header') }} mh USING (match_id)
),

shots_enriched AS (
    SELECT
        s.*,
        mh.competition_phase,

        sqrt(s.norm_pos_x * s.norm_pos_x + s.norm_pos_y * s.norm_pos_y) AS dist,
        degrees(atan2(s.norm_pos_y, abs(s.norm_pos_x))) AS ang,

        mh.home_team_id,
        mh.away_team_id,
        mh.home_team_club_id,
        mh.away_team_club_id,

        coalesce(
            r.team_id,
            CASE WHEN s.is_local_team THEN mh.home_team_id ELSE mh.away_team_id END
        ) AS team_id,

        p.event_idx,
        coalesce(p.is_assisted, FALSE) AS is_assisted,
        coalesce(p.is_and_one, FALSE) AS is_and_one,
        (s.play_type IN (100, 533)) AS is_dunk,

        (s.play_type IN (92, 93, 94, 100)) AS is_made,

        CASE
            WHEN s.play_type IN (94, 98) THEN 3
            WHEN s.play_type IN (92, 96) THEN 1
            ELSE 2
        END AS shot_value

    FROM shots_numbered s
    LEFT JOIN mh USING (match_id)
    LEFT JOIN roster r
        ON r.match_id = s.match_id
       AND r.player_id = s.player_id
    LEFT JOIN pbp_shots p
        ON p.match_id = s.match_id
       AND p.quarter = s.quarter
       AND p.minute = s.minute
       AND p.second = s.second
       AND p.player_id = s.player_id
       AND p.play_type_id = s.play_type
       AND p.occurrence = s.occurrence
),

geom_zones AS (
    SELECT
        se.*,
        cz.zone_id AS geom_zone_id,
        ROW_NUMBER() OVER (
            PARTITION BY se.match_id, se.shot_id
            ORDER BY cz.zone_id
        ) AS zone_rank
    FROM shots_enriched se
    LEFT JOIN {{ ref('court_zones') }} cz
        ON cz.zone_id BETWEEN 1 AND 12
       AND se.dist BETWEEN cz.dist_min AND cz.dist_max
       AND se.ang BETWEEN cz.ang_min AND cz.ang_max
),

final AS (
    SELECT
        *,
        CASE
            WHEN play_type IN (92, 96) THEN 14
            WHEN dist > 14000 THEN 13
            ELSE geom_zone_id
        END AS zone_id
    FROM geom_zones
    WHERE zone_rank = 1
)

SELECT
    concat_ws('_', match_id, shot_id) AS id,

    shot_id,
    competition_id,
    competition_phase,
    edition_id,
    match_id,
    player_id,
    team_id,
    CASE WHEN team_id = home_team_id THEN home_team_club_id ELSE away_team_club_id END AS club_id,
    home_team_id,
    away_team_id,

    play_type AS play_type_id,
    event_idx,
    is_dunk,
    is_assisted,
    is_and_one,

    norm_pos_y AS x,
    norm_pos_x AS y,

    zone_id,
    is_made,
    shot_value,

    round(dist, 2) AS distance_mm,
    round(ang, 2) AS angle_deg,

    quarter,
    minute,
    second,
    score_home,
    score_away,

    cat_insert_date
FROM final