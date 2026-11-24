{{ config(
    materialized='table',
    schema = "staging",
    tags=["acb_analytics"]
) }}

-- Ficha biográfica de cada jugador (web de la ACB). Fecha en formato dd-mm-aaaa y altura en
-- metros con coma ("2,02").
SELECT
    try_cast(player_id AS INT) AS player_id,
    -- birthDate llega como DATE (si DuckDB lo detecta) o como texto dd-mm-aaaa: se aceptan ambos
    try_strptime(nullif(birthDate::VARCHAR, ''), ['%d-%m-%Y', '%Y-%m-%d'])::DATE AS birth_date,
    nullif(trim(birthPlace::VARCHAR), '') AS birth_place,
    nullif(trim(birthCountry::VARCHAR), '') AS birth_country,
    nullif(trim(nationality::VARCHAR), '') AS nationality,
    try_cast(replace(nullif(height::VARCHAR, ''), ',', '.') AS DOUBLE) AS height_m
FROM {{ source('acb_landing', 'player_bios') }}
WHERE player_id IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY try_cast(player_id AS INT)) = 1
