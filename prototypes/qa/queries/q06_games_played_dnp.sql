-- Apariciones sin minutos (DNP) por edición: ya no cuentan como partido jugado
SELECT edition_id,
       count(*) AS player_game_rows,
       count(*) FILTER (WHERE seconds = 0) AS dnp_rows
FROM main_marts.fact_player_games
GROUP BY edition_id
ORDER BY edition_id;
