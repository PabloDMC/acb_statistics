{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Un club es la identidad que persiste entre temporadas; cada temporada y competición participa
-- con un team_id distinto y, a menudo, con otro nombre comercial. `club_name` es el nombre fijo
-- del seed club_names; si un club aún no está en el seed se usa su último nombre de equipo.

WITH teams AS (
    SELECT *
    FROM {{ ref('int_teams') }}
),

latest AS (
    SELECT
        club_id,
        -- la liga regular manda sobre copa y supercopa a igualdad de temporada
        arg_max(full_name, edition_id * 10 - competition_id) AS latest_team_name,
        arg_max(short_name, edition_id * 10 - competition_id) AS latest_short_name,
        arg_max(abbr, edition_id * 10 - competition_id) AS latest_abbr,
        arg_max(logo, edition_id * 10 - competition_id) AS logo,
        arg_max(primary_color, edition_id * 10 - competition_id) AS primary_color,
        min(edition_id) AS first_edition_id,
        max(edition_id) AS last_edition_id,
        count(DISTINCT edition_id) AS editions
    FROM teams
    WHERE club_id IS NOT NULL
    GROUP BY club_id
)

SELECT
    l.club_id,
    coalesce(n.club_name, l.latest_team_name) AS club_name,
    l.latest_team_name,
    l.latest_short_name,
    l.latest_abbr,
    l.logo,
    l.primary_color,
    l.first_edition_id,
    l.last_edition_id,
    l.editions
FROM latest l
LEFT JOIN {{ ref('club_names') }} n
    USING (club_id)
