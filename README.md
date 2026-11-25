# acb_statistics

Estadísticas de la Liga ACB (Liga Endesa, Copa del Rey y Supercopa) desde 1983-84 (con jugada a jugada,
quintetos y cartas de tiro desde 2016-17; antes, la ACB solo publica el boxscore final):
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

4. **Con Docker** (opcional, igual que en producción): `docker compose up --build` levanta API
   (http://localhost:8000/docs) y app (http://localhost:8501) usando la base de `data/database`.

## Despliegue (gratis)

La web pública vive en **Streamlit Community Cloud** (gratis, sin tarjeta). Community Cloud solo
ejecuta Streamlit, así que la app arranca la API dentro, como proceso hijo en `127.0.0.1:8000`, sin
exponerla (`src/app/backend.py`). La base no va en git: está en un **dataset privado de Hugging
Face**, la app la descarga al arrancar y cada hora mira si hay una versión nueva.

Configuración, una sola vez:

1. En Hugging Face, un token de escritura (para publicar desde tu PC) y otro de solo lectura (para
   la web). En `.env`: `HF_TOKEN` (escritura) y `ACB_DB_DATASET` (p. ej. `usuario/acb-statistics-db`).
2. `python scripts/publish_db.py --force` sube la base al dataset (se crea solo, privado).
3. En https://share.streamlit.io, con tu cuenta de GitHub: *Create app* → repositorio
   `PabloDMC/acb_statistics`, rama `main`, archivo `src/app/streamlit_app.py`, Python 3.12. En
   *Advanced settings → Secrets*:
   ```
   ACB_DB_DATASET = "usuario/acb-statistics-db"
   HF_TOKEN = "hf_...token de solo lectura..."
   ```
   Cada push a `main` redespliega la app solo. Las dependencias salen de `src/app/requirements.txt`.
4. `.\scripts\scheduled_update.ps1 -Register` programa en Windows la actualización diaria
   (05:30, o al encender el PC si estaba apagado): ingesta + dbt + publicar. Si no hay partidos
   nuevos no sube nada; si los hay, la web los muestra en menos de una hora.

`deploy/` y `docker-compose.yml` sirven para levantarlo todo con Docker, en local o en cualquier
servidor con Docker, si algún día se deja Community Cloud.

## Estructura

- `src/ingestion`: descarga de la API de la ACB a `data/landing`.
- `dbt_acb`: modelos de transformación y tests.
- `src/api`: API de consumo (FastAPI, solo lectura sobre DuckDB).
- `src/app`: app de Streamlit (`views/` tiene una página por entidad: temporada, jugador, equipo, partido).
- `scripts/update_data.py`: ingesta + dbt en un comando.
- `scripts/publish_db.py`, `scripts/scheduled_update.ps1`: publicación de la base y actualización
  programada. `deploy/`: imagen Docker.
- `scripts/probe_history.py`: sondeo de qué datos ofrece la API en temporadas antiguas.
- `prototypes/qa`: consultas de QA contra la base de datos (`run_sql.py`).
