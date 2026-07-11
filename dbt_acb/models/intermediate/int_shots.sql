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

        play_type,
        quarter,
        minute,
        second,
        is_local_team,
        score_home,
        score_away,

        cat_insert_date
    FROM {{ ref('stg_apiacb__match_shots') }}
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

        CASE WHEN s.is_local_team
             THEN mh.home_team_id
             ELSE mh.away_team_id
        END AS team_id,

        CASE WHEN s.is_local_team
             THEN mh.home_team_club_id
             ELSE mh.away_team_club_id
        END AS club_id,

        (s.play_type IN (92, 93, 94, 100)) AS is_made,

        CASE
            WHEN s.play_type IN (94, 98) THEN 3
            WHEN s.play_type IN (92, 96) THEN 1
            ELSE 2
        END AS shot_value

    FROM shots s
    LEFT JOIN mh USING (match_id)
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
    club_id,

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