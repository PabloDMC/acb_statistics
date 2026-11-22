# acb_statistics

Estadísticas de la Liga ACB (Liga Endesa, Copa del Rey y Supercopa) desde 2016-17:
ingesta de la API de la ACB → JSON en `data/landing` → DuckDB → dbt (staging, intermediate,
marts) → API FastAPI → app Streamlit.

## Puesta en marcha

Con el entorno virtual activado, desde la raíz del proyecto:

```
pip install -r requirements.txt
```

1. **Actualizar los datos** (con la API parada, porque dbt escribe en la base de datos):
   ```
   python scripts/update_data.py                  # temporada en curso, tras cada jornada
   python scripts/update_data.py --editions 90 91 # temporadas concretas
   python scripts/update_data.py --skip-ingest    # solo dbt
   python scripts/update_data.py --full-refresh   # dbt build --full-refresh
   ```
2. **API** (documentación en http://localhost:8000/docs y en `src/api/README.md`):
   ```
   cd src/api
   uvicorn app.main:app --reload
   ```
3. **App** (en otra terminal, desde la raíz; abre http://localhost:8501):
   ```
   streamlit run src/app/streamlit_app.py
   ```
   La app solo habla con la API. Si la API no está en `http://localhost:8000/api/v1`, indícalo
   con la variable de entorno `ACB_API_URL`.

## Estructura

- `src/ingestion`: descarga de la API de la ACB a `data/landing`.
- `dbt_acb`: modelos de transformación y tests.
- `src/api`: API de consumo (FastAPI, solo lectura sobre DuckDB).
- `src/app`: app de Streamlit (`views/` tiene una página por entidad: temporada, jugador, equipo, partido).
- `scripts/update_data.py`: ingesta + dbt en un comando.
- `prototypes/qa`: consultas de QA contra la base de datos (`run_sql.py`).
