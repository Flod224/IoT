"""
Configuration centralisée pour le backend SmartIGLab
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application"""
    
    # Serveur
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Capacité
    room_capacity: int = 40
    
    # GPIO (Raspberry Pi, BCM numbering)
    dht22_pin: int = 4
    reed_switch_pin: int = 17
    sensor_read_interval: float = 10.0
    
    # Vision YOLO
    vision_enabled: bool = True
    cam_index: int = 0
    cam_width: int = 640
    cam_height: int = 480
    yolo_model: str = "yolov8n.pt"
    yolo_conf: float = 0.5
    yolo_imgsz: int = 640
    update_interval: float = 0.5
    
    # Hyperplanning
    hyperplanning_enabled: bool = False
    hyperplanning_url: str = ""
    hyperplanning_room_id: str = ""
    hyperplanning_refresh_interval: float = 300.0
    
    # CORS
    cors_origins: str = "*"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instance globale
settings = Settings()
