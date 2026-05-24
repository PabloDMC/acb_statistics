import os
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any
from src.api_acb_client import ApiAcbClient
from src.config import (
    ACB_BASE_URL, 
    ACB_API_KEY, 
    LANDING_DIR, 
    COMPETITIONS, 
    MAX_WORKERS
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
LOG = logging.getLogger("ACB_Ingestion")


# ==============================================================================
# PARSEO DE PAYLOADS
# ==============================================================================
def extract_round_ids(competition_payload: Dict[str, Any]) -> List[Tuple[int, int]]:
    """Extrae tuplas de (edition_id, round_id) desde el payload de competición."""
    round_ids = []
    competitions = competition_payload.get("competitions", [])
    for competition in competitions:
        for edition in competition.get("editions", []):
            edition_id = edition.get("id")
            for rnd in edition.get("rounds", []):
                round_id = rnd.get("id")
                if round_id is not None and edition_id is not None:
                    round_ids.append((edition_id, round_id))
    return round_ids

def extract_match_ids(matchlist_payload: Dict[str, Any]) -> List[Tuple[int, int]]:
    """Extrae tuplas de (edition_id, match_id) desde el listado de partidos de una ronda."""
    match_ids = []
    edition_id = matchlist_payload.get("editionId")
    if edition_id is not None:
        for match in matchlist_payload.get("matches", []):
            match_id = match.get("id")
            if match_id is not None:
                match_ids.append((edition_id, match_id))
    return match_ids


# ==============================================================================
# PERSISTENCIA IDEMPOTENTE (Estructura plana para dbt)
# ==============================================================================
def save_json_file(dataset: str, filename: str, data: dict):
    """Guarda un archivo JSON asegurando que exista su subcarpeta en Landing."""
    target_dir = os.path.join(LANDING_DIR, dataset)
    os.makedirs(target_dir, exist_ok=True)
    
    path = os.path.join(target_dir, f"{filename}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==============================================================================
# HILO DE EJECUCIÓN POR PARTIDO
# ==============================================================================
def ingest_match_task(api_client: ApiAcbClient, match_info: Tuple[int, int]):
    """ Procesa la descarga del Header y sub-datasets de forma optimizada. """
    edition_id, match_id = match_info
    filename = f"ed_{edition_id}_m_{match_id}"
    
    header_path = os.path.join(LANDING_DIR, "match_header", f"{filename}.json")
    header_data = None

    try:
        # Chequeo en disco para evitar llamadas repetidas al Header
        if os.path.exists(header_path):
            with open(header_path, "r", encoding="utf-8") as f:
                header_data = json.load(f)
        else:
            header_data = api_client.get_match_header(match_id)
            if not header_data:
                return
            
            # Solo consolidamos de forma fija el Header si el partido ha terminado
            if header_data.get('matchStatus') == 'FINALIZED':
                save_json_file("match_header", filename, header_data)

        # Si el partido no ha terminado, sus estadísticas están incompletas -> Nos lo saltamos
        if header_data.get('matchStatus') != 'FINALIZED':
            return

        # Mapeo según disponibilidad informada en el JSON del Header
        content = header_data.get('availableContent', {})
        sub_datasets = {
            "boxscore": True, 
            "play_by_play": content.get('playbyplay', False),
            "match_shots": content.get('playbyplay', False) 
        }

        for dataset_name, is_available in sub_datasets.items():
            if is_available:
                dest_file = os.path.join(LANDING_DIR, dataset_name, f"{filename}.json")
                
                # Si el archivo analítico ya existe continuamos
                if os.path.exists(dest_file):
                    continue
                
                try:
                    # Invocamos dinámicamente el método correcto en el cliente
                    method = getattr(api_client, f"get_{dataset_name}")
                    data = method(match_id)
                    if data:
                        save_json_file(dataset_name, filename, data)
                except Exception as e:
                    LOG.error(f"Error en sub-dataset {dataset_name} para partido {match_id}: {e}")

    except Exception as e:
        LOG.error(f"Error procesando el hilo del partido {match_id}: {e}")


# ==============================================================================
# FLUX COORDINATOR (Orquestador Central)
# ==============================================================================
def run_pipeline(is_incremental: bool = False, target_editions: list = None):
    """
    Controla la estrategia de extracción.
    is_incremental=True: Descarga exclusivamente la temporada en curso activa.
    target_editions=[...]: Descarga un set histórico específico.
    """
    LOG.info(f"Arrancando Ingesta ACB (Incremental: {is_incremental})")

    api_client = ApiAcbClient(base_url=ACB_BASE_URL, api_key=ACB_API_KEY)
    
    active_round_ids = set()
    all_match_tasks = set()

    # Fase 1: Descarga e inspección de Rondas de las Competiciones elegidas
    for comp_id in COMPETITIONS:
        payload = api_client.get_competition(comp_id)
        if not payload:
            continue
            
        save_json_file("competition", f"comp_{comp_id}", payload)
        curr_edition = payload.get("currentEditionId")
        all_rounds = extract_round_ids(payload)
        
        if is_incremental:
            active_round_ids.update([r for r in all_rounds if r[0] == curr_edition])
        elif target_editions:
            active_round_ids.update([r for r in all_rounds if r[0] in target_editions])
        else:
            active_round_ids.update(all_rounds)

    # Fase 2: Recopilación de Matchlists (Listas de partidos por ronda)
    LOG.info(f"Analizando {len(active_round_ids)} rondas de competición...")
    for edition_id, round_id in active_round_ids:
        filename = f"ed_{edition_id}_rnd_{round_id}"
        matchlist_path = os.path.join(LANDING_DIR, "matchlist", f"{filename}.json")
        
        if os.path.exists(matchlist_path):
            with open(matchlist_path, "r", encoding="utf-8") as f:
                ml_payload = json.load(f)
        else:
            ml_payload = api_client.get_matchlist(round_id)
            if not ml_payload:
                continue
                
            # Si en la ronda entera no hay partidos jugados aún, evitamos escribir un JSON vacío
            matches = ml_payload.get("matches", [])
            if not any(m.get("matchStatus") == "FINALIZED" for m in matches):
                continue
                
            save_json_file("matchlist", filename, ml_payload)
            
        all_match_tasks.update(extract_match_ids(ml_payload))

    # Fase 3: Lanzamiento del Pool de Hilos para descarga en paralelo
    if all_match_tasks:
        LOG.info(f"Evaluando descargas para un total de {len(all_match_tasks)} partidos...")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(ingest_match_task, api_client, task) for task in all_match_tasks]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    LOG.error(f"Fallo en ejecución de hilo: {e}")
                    
        LOG.info("Pipeline completado con éxito.")
    else:
        LOG.info("No se han detectado partidos nuevos que descargar.")


if __name__ == "__main__":
    run_pipeline(is_incremental=True)
    
    # run_pipeline(is_incremental=False, target_editions=list(range(80, 91)))