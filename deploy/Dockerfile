# Imagen única para servir la app: API (FastAPI, interna) + Streamlit (pública).
# docker-compose.yml la usa para levantar los dos servicios en local; sirve también para llevar la
# app a cualquier servidor con Docker (la web pública está en Streamlit Community Cloud).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    ACB_DUCKDB_PATH=/data/acb_analytics.duckdb \
    ACB_API_URL=http://127.0.0.1:8000/api/v1

WORKDIR /app
COPY src/app/requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY src/__init__.py src/__init__.py
COPY src/api src/api
COPY src/app src/app
COPY .streamlit .streamlit
COPY deploy/start.sh deploy/start.sh

# Hugging Face ejecuta los contenedores con el usuario 1000; /data es donde se descarga la base
RUN useradd -m -u 1000 user && mkdir -p /data && chown -R user /data /app && chmod +x deploy/start.sh
USER user

EXPOSE 7860
CMD ["deploy/start.sh"]
