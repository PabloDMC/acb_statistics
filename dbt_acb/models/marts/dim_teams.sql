{{ config(
    materialized='table',
    schema='marts',
    tags=['acb_analytics']
) }}

-- Un team_id es la participación de un club en UNA competición de UNA temporada: no se repite
-- entre competiciones ni entre temporadas.

SELECT

    t.team_id,
    t.club_id,
    c.club_name,

    t.edition_id,
    t.competition_id,

    t.full_name,
    t.short_name,
    t.abbr,

    t.logo,
    t.secondary_logo,

    t.primary_color,
    t.text_color,

    t.cat_insert_date

FROM {{ ref('int_teams') }} t
LEFT JOIN {{ ref('dim_clubs') }} c
    USING (club_id)
