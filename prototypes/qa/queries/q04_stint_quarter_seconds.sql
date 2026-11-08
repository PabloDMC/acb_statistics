-- Tras el arreglo del reloj: cuartos cuyos tramos no suman 600 s (300 en prórroga), por equipo
SELECT match_id, quarter, sum(seconds) AS seconds,
       CASE WHEN quarter <= 4 THEN 600 ELSE 300 END AS expected
FROM main_intermediate.int_stints
GROUP BY match_id, quarter
HAVING sum(seconds) <> CASE WHEN quarter <= 4 THEN 600 ELSE 300 END
ORDER BY match_id, quarter;
