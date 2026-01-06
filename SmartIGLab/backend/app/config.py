"""
SmartIGLab - Configuration Backend
==================================
Configuration centralisée avec Pydantic Settings.
Valeurs par défaut overridables via fichier .env
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuration principale du backend SmartIGLab
    
    Toutes les valeurs peuvent être overridées via:
    - Fichier .env dans backend/app/.env
    - Variables d'environnement système
    """
    
    # === SERVEUR ===
    host: str = "0.0.0.0"  # Écoute sur toutes les interfaces réseau
    port: int = 8000  # Port HTTP par défaut
    debug: bool = False  # Mode debug (logs verbeux)
    
    # === SALLE ===
    room_capacity: int = 40  # Capacité maximale de la salle
    
    # === GPIO RASPBERRY PI ===
    # Numérotation BCM (pas physique)
    dht22_pin: int = 4  # Pin GPIO4 pour capteur température/humidité
    reed_switch_pin: int = 17  # Pin GPIO17 pour détecteur fenêtre
    sensor_read_interval: float = 10.0  # Lecture capteurs toutes les 10s
    
    # === VISION YOLO (Comptage de personnes) ===
    vision_enabled: bool = True  # Activer/désactiver la caméra
    cam_index: int = 0  # Index caméra USB (/dev/video0)
    cam_width: int = 640  # Résolution largeur
    cam_height: int = 480  # Résolution hauteur
    yolo_model: str = "yolov8n.pt"  # Modèle YOLO (nano pour Raspberry Pi)
    yolo_conf: float = 0.5  # Seuil de confiance détection (0-1)
    yolo_imgsz: int = 640  # Taille image YOLO
    update_interval: float = 0.5  # Rafraîchissement vision (0.5s = 2 FPS)
    
    # === HYPERPLANNING (Emploi du temps) ===
    hyperplanning_enabled: bool = True  # Activer le module planning
    hyperplanning_use_ics: bool = False  # False=JSON, True=ICS
    hyperplanning_refresh_interval: float = 60.0  # Mise à jour toutes les 1min
    
    cors_origins: str = "*"  # Origins CORS autorisées (GET uniquement)
    
    # === AUTHENTIFICATION (DÉFINIR DANS .env) ===
    dashboard_username: str = "admin"  # Par défaut, CHANGER dans .env!
    dashboard_password: str = "changeme"  # Par défaut, CHANGER dans .env!
    
    class Config:
        """Configuration Pydantic"""
        env_file = Path(__file__).parent / ".env"  # Fichier .env dans app/
        case_sensitive = False  # Variables en minuscules ou majuscules


# Instance globale unique utilisée par toute l'application
settings = Settings()
