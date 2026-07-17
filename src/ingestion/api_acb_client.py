import requests
import logging
from typing import Optional, Dict, Any

LOG = logging.getLogger(__name__)

class ApiAcbClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/') 
        self.headers = {
            "user-agent": "Mozilla/5.0",
            "referer": "https://live.acb.com",
            "x-apikey": api_key,
            "Accept": "application/json"
        }

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Método base privado para ejecutar las peticiones HTTP."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            LOG.error(f"Error en petición ACB a {url}: {str(e)}")
            return None

    def get_competition(self, competition_id: int) -> Optional[Dict[str, Any]]:
        return self._get("/Menu/competition-data", params={"competitionIds": competition_id})

    def get_matchlist(self, round_id: int) -> Optional[Dict[str, Any]]:
        return self._get("/Menu/matchlist", params={"roundId": round_id})

    def get_match_header(self, match_id: int) -> Optional[Dict[str, Any]]:
        return self._get("/MatchHeader/match-header", params={"matchId": match_id})

    def get_match_shots(self, match_id: int) -> Optional[Dict[str, Any]]:
        return self._get("/MatchShots/match-shots", params={"matchId": match_id})

    def get_play_by_play(self, match_id: int) -> Optional[Dict[str, Any]]:
        return self._get("/PlayByPlay/play-by-play", params={"matchId": match_id})

    def get_boxscore(self, match_id: int) -> Optional[Dict[str, Any]]:
        return self._get("/Result/boxscores", params={"matchId": match_id})