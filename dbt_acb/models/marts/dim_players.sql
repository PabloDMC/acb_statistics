{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Una fila por jugador, con los datos de su ficha más reciente (dim_rosters es jugador x equipo).

WITH rosters AS (
    SELECT *
    FROM {{ ref('dim_rosters') }}
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY player_id
            ORDER BY end_date DESC NULLS LAST, edition_id DESC, competition_id
        ) AS rn
    FROM rosters
),

career AS (
    SELECT
        player_id,
        min(edition_id) AS first_edition_id,
        max(edition_id) AS last_edition_id,
        count(DISTINCT edition_id) AS editions,
        min(start_date) AS first_match_date,
        max(end_date) AS last_match_date
    FROM rosters
    GROUP BY player_id
)

SELECT
    r.player_id,
    r.player_name,
    r.player_first_name,
    r.player_last_name,
    r.player_first_initial_and_last_name,
    r.player_nickname,
    r.player_shirt_number,
    r.player_roles_concat,
    r.player_headshot_image_url,
    r.player_headshot_image_no_background_url,
    r.player_is_license_active,
    r.team_id AS latest_team_id,
    r.club_id AS latest_club_id,
    c.first_edition_id,
    c.last_edition_id,
    c.editions,
    c.first_match_date,
    c.last_match_date
FROM ranked r
JOIN career c
    USING (player_id)
WHERE r.rn = 1
