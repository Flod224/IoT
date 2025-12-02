"""
Module Hyperplanning (stub pour l'instant)
"""

import time
import logging
from typing import Optional
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class HyperplanningClient:
    """Client Hyperplanning pour récupérer l'état des cours"""
    
    def __init__(self, url: str, room_id: str, refresh_interval: float = 300.0):
        self.url = url
        self.room_id = room_id
        self.refresh_interval = refresh_interval
        
        # État partagé
        self._lock = Lock()
        self._state = "unknown"  # "libre", "course_en_cours", "course_prevue"
        self._title: Optional[str] = None
        self._start_time: Optional[str] = None
        self._end_time: Optional[str] = None
        self._last_update: Optional[float] = None
        self._running = False
        
        self._thread: Optional[Thread] = None
    
    def get_status(self) -> dict:
        """Retourne l'état actuel (thread-safe)"""
        with self._lock:
            return {
                "state": self._state,
                "title": self._title,
                "start_time": self._start_time,
                "end_time": self._end_time,
                "last_update": self._last_update
            }
    
    def _fetch_planning(self):
        """Récupère les données depuis Hyperplanning (à implémenter)"""
        # TODO: implémenter requête HTTP vers Hyperplanning API
        # Pour l'instant, retourne données mockées
        
        logger.debug("Récupération planning (mock)")
        
        # Simulation: libre entre 12h-14h, occupé sinon
        import datetime
        now = datetime.datetime.now()
        hour = now.hour
        
        if 12 <= hour < 14:
            return {
                "state": "libre",
                "title": None,
                "start_time": None,
                "end_time": None
            }
        else:
            return {
                "state": "course_en_cours",
                "title": "Cours IoT - MA2",
                "start_time": "14:00",
                "end_time": "17:00"
            }
    
    def _update_state(self, data: dict):
        """Met à jour l'état (thread-safe)"""
        with self._lock:
            self._state = data.get("state", "unknown")
            self._title = data.get("title")
            self._start_time = data.get("start_time")
            self._end_time = data.get("end_time")
            self._last_update = time.time()
    
    def _run_loop(self):
        """Boucle de refresh (thread)"""
        logger.info(f"Démarrage Hyperplanning client (intervalle: {self.refresh_interval}s)")
        
        while self._running:
            try:
                data = self._fetch_planning()
                self._update_state(data)
                logger.info(f"Hyperplanning: état={data['state']}")
            except Exception as e:
                logger.error(f"Erreur récupération planning: {e}")
            
            time.sleep(self.refresh_interval)
        
        logger.info("Boucle Hyperplanning arrêtée")
    
    def start(self):
        """Démarre le client"""
        if self._running:
            logger.warning("Client Hyperplanning déjà en cours")
            return
        
        if not self.url:
            logger.warning("URL Hyperplanning non configurée - mode mock")
        
        self._running = True
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Client Hyperplanning démarré")
    
    def stop(self):
        """Arrête le client"""
        if not self._running:
            return
        
        logger.info("Arrêt client Hyperplanning...")
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
