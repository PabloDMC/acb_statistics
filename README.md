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

La web pública vive en un **Space de Hugging Face** (Docker). Un solo contenedor sirve la app de
Streamlit en el puerto público y la API dentro, en `127.0.0.1:8000`, sin exponerla. La base no va
en git: se guarda en un **dataset privado de Hugging Face** y el contenedor la descarga al arrancar.

Configuración, una sola vez:

1. Crea una cuenta en https://huggingface.co y un token con permiso de escritura
   (Settings → Access Tokens). Copia `.env.example` como `.env` y rellena `HF_TOKEN`,
   `ACB_DB_DATASET` y `HF_SPACE` (el dataset y el Space se crean solos la primera vez).
2. `python scripts/publish_db.py --force` sube la base al dataset.
3. `python scripts/deploy_space.py` sube el código al Space. Desde entonces, cada push a `main` que
   toque la app lo vuelve a desplegar (`.github/workflows/deploy-space.yml`). Para eso, en GitHub
   → Settings → Secrets and variables → Actions: secreto `HF_TOKEN` y variables `HF_SPACE` y
   `ACB_DB_DATASET`.
4. `.\scripts\scheduled_update.ps1 -Register` programa en Windows la actualización diaria
   (05:30, o al encender el PC si estaba apagado): ingesta + dbt + publicar. Si no hay partidos
   nuevos no sube nada. Registro en `logs/`.

## Estructura

- `src/ingestion`: descarga de la API de la ACB a `data/landing`.
- `dbt_acb`: modelos de transformación y tests.
- `src/api`: API de consumo (FastAPI, solo lectura sobre DuckDB).
- `src/app`: app de Streamlit (`views/` tiene una página por entidad: temporada, jugador, equipo, partido).
- `scripts/update_data.py`: ingesta + dbt en un comando.
- `scripts/publish_db.py`, `scripts/deploy_space.py`, `scripts/scheduled_update.ps1`, `deploy/`:
  publicación en Hugging Face y actualización programada.
- `scripts/probe_history.py`: sondeo de qué datos ofrece la API en temporadas antiguas.
- `prototypes/qa`: consultas de QA contra la base de datos (`run_sql.py`).
