"""
Modèles de données pour l'API
"""

from typing import Optional
from pydantic import BaseModel


class EnvironmentData(BaseModel):
    """Données environnementales"""
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    window_open: Optional[bool] = None
    last_update: Optional[float] = None


class HyperplanningData(BaseModel):
    """Données Hyperplanning"""
    state: str = "unknown"  # "unknown", "libre", "course_en_cours", "course_prevue"
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class SystemStatus(BaseModel):
    """Statut complet du système"""
    occupied: bool
    free_seats: int
    people_count: int
    capacity: int
    environment: EnvironmentData
    hyperplanning: HyperplanningData
    vision_fps: float
    updated_at: float


class HealthResponse(BaseModel):
    """Réponse healthcheck"""
    status: str
    vision_running: bool
    sensors_running: bool
    uptime: float
