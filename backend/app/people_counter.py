#!/usr/bin/env python3
"""
SmartIGLab - Vision Module (Standalone)
Comptage de personnes avec YOLOv8n - retourne le nombre en mémoire
"""

import os
import sys
import time
import logging
from typing import Optional
from pathlib import Path
from threading import Thread, Lock

import cv2
import numpy as np
from ultralytics import YOLO

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vision")


class Config:
    """Configuration chargée depuis variables d'environnement"""
    def __init__(self):
        # Caméra
        self.cam_index = int(os.getenv("CAM_INDEX", "0"))
        self.cam_width = int(os.getenv("CAM_WIDTH", "640"))
        self.cam_height = int(os.getenv("CAM_HEIGHT", "480"))
        
        # YOLO
        self.yolo_model = os.getenv("YOLO_MODEL", "yolov8n.pt")
        self.yolo_conf = float(os.getenv("YOLO_CONF", "0.5"))
        self.yolo_imgsz = int(os.getenv("YOLO_IMGSZ", "640"))
        
        # Paramètres
        self.room_capacity = int(os.getenv("ROOM_CAPACITY", "40"))
        self.show_video = os.getenv("SHOW_VIDEO", "False").lower() == "true"
        self.update_interval = float(os.getenv("UPDATE_INTERVAL", "0.5"))


class PeopleCounter:
    """Compteur de personnes avec YOLO - Thread-safe"""
    
    def __init__(self, config: Config):
        self.config = config
        self.model: Optional[YOLO] = None
        self.cap: Optional[cv2.VideoCapture] = None
        
        # État partagé (thread-safe)
        self._lock = Lock()
        self._people_count = 0
        self._fps = 0.0
        self._last_update = time.time()
        self._running = False
        
        # Thread
        self._thread: Optional[Thread] = None
        
    @property
    def people_count(self) -> int:
        """Nombre de personnes détectées (thread-safe)"""
        with self._lock:
            return self._people_count
    
    @property
    def fps(self) -> float:
        """FPS actuel (thread-safe)"""
        with self._lock:
            return self._fps
    
    @property
    def last_update(self) -> float:
        """Timestamp dernière mise à jour (thread-safe)"""
        with self._lock:
            return self._last_update
    
    def get_status(self) -> dict:
        """Retourne le statut complet (thread-safe)"""
        with self._lock:
            return {
                "people_count": self._people_count,
                "fps": round(self._fps, 1),
                "capacity": self.config.room_capacity,
                "free_seats": max(0, self.config.room_capacity - self._people_count),
                "last_update": self._last_update,
                "is_running": self._running
            }
        
    def setup_model(self):
        """Initialise le modèle YOLO"""
        logger.info(f"Chargement du modèle {self.config.yolo_model}...")
        try:
            self.model = YOLO(self.config.yolo_model)
            logger.info("Modèle chargé avec succès")
        except Exception as e:
            logger.error(f"Erreur chargement modèle: {e}")
            raise RuntimeError(f"Impossible de charger le modèle YOLO: {e}") from e
    
    def setup_camera(self):
        """Initialise la caméra"""
        logger.info(f"Initialisation caméra index {self.config.cam_index}...")
        self.cap = cv2.VideoCapture(self.config.cam_index)
        
        if not self.cap.isOpened():
            logger.error("Impossible d'ouvrir la caméra")
            raise RuntimeError(f"Impossible d'ouvrir la caméra à l'index {self.config.cam_index}")
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.cam_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.cam_height)
        
        # Test lecture
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Impossible de lire le flux caméra")
            self.cap.release()
            raise RuntimeError("Impossible de lire le flux de la caméra")
        
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Caméra initialisée: {actual_width}x{actual_height}")
    
    def _update_state(self, count: int, fps: float):
        """Met à jour l'état interne (thread-safe)"""
        with self._lock:
            self._people_count = count
            self._fps = fps
            self._last_update = time.time()
    
    def detect_people(self, frame: np.ndarray) -> int:
        """
        Détecte les personnes dans une frame
        Returns: nombre de personnes détectées
        """
        results = self.model(
            frame,
            imgsz=self.config.yolo_imgsz,
            conf=self.config.yolo_conf,
            classes=[0],  # class 0 = person dans COCO
            verbose=False
        )
        
        # Extraire les détections
        boxes = results[0].boxes
        count = len(boxes) if boxes is not None else 0
        
        # Affichage debug si activé
        if self.config.show_video and boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"Person {conf:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return count
    
    def _run_loop(self):
        """Boucle de détection (s'exécute dans un thread)"""
        logger.info("Démarrage de la boucle de détection...")
        
        frame_count = 0
        last_time = time.time()
    
        try:
            while self._running:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Impossible de lire la frame, attente...")
                    time.sleep(0.2)
                    continue
                
                # Détection
                count = self.detect_people(frame)
                frame_count += 1
                
                # Calcul FPS et mise à jour
                now = time.time()
                elapsed = now - last_time
                
                if elapsed >= self.config.update_interval:
                    fps = frame_count / elapsed
                    self._update_state(count, fps)
                    
                    logger.info(f"Personnes: {count}, FPS: {fps:.1f}")
                    
                    # Reset compteurs
                    frame_count = 0
                    last_time = now
                
                # Affichage debug
                if self.config.show_video:
                    cv2.putText(frame, f"Personnes: {count}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(frame, f"FPS: {self._fps:.1f}", (10, 70),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.imshow("SmartIGLab Vision", frame)
                    
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("Arrêt demandé par l'utilisateur")
                        self.stop()
                        break
        
        except Exception as e:
            logger.error(f"Erreur dans la boucle de détection: {e}", exc_info=True)
        finally:
            logger.info("Boucle de détection arrêtée")
    
    def start(self):
        """Démarre le compteur en arrière-plan"""
        if self._running:
            logger.warning("Le compteur est déjà en cours d'exécution")
            return
        
        self.setup_model()
        self.setup_camera()
        
        self._running = True
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Compteur démarré en arrière-plan")
    
    def stop(self):
        """Arrête le compteur"""
        if not self._running:
            return
        
        logger.info("Arrêt du compteur...")
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        self.cleanup()
    
    def cleanup(self):
        """Nettoyage des ressources"""
        if self.cap:
            self.cap.release()
            self.cap = None
        
        if self.config.show_video:
            cv2.destroyAllWindows()
        
        logger.info("Ressources libérées")
    
    def run_blocking(self):
        """Exécute le compteur en mode bloquant (pour tests)"""
        self.setup_model()
        self.setup_camera()
        self._running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            logger.info("Interruption clavier")
        finally:
            self.cleanup()


def load_env_file():
    """Charge les variables depuis .env si présent"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        logger.info(f"Chargement de {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    if key and value:
                        os.environ[key.strip()] = value.strip()


def main():
    """Point d'entrée pour test standalone"""
    load_env_file()
    
    config = Config()
    counter = PeopleCounter(config)
    
    # Mode bloquant pour test CLI
    counter.run_blocking()


if __name__ == "__main__":
    main()
