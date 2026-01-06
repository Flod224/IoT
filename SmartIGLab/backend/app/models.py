"""
SmartIGLab - Modèles de données API
====================================
Schémas Pydantic pour validation et sérialisation JSON
"""

from typing import Optional
from pydantic import BaseModel, Field


class EnvironmentData(BaseModel):
    """
    Données environnementales de la salle
    Provenant des capteurs GPIO (DHT22 + reed switch)
    """
    temperature: Optional[float] = Field(None, description="Température en °C")
    humidity: Optional[float] = Field(None, description="Humidité relative en %")
    window_open: Optional[bool] = Field(None, description="Fenêtre ouverte (True) ou fermée (False)")
    last_update: Optional[float] = Field(None, description="Timestamp dernière lecture capteur")


class HyperplanningData(BaseModel):
    """
    Données d'emploi du temps
    État actuel des cours dans la salle
    """
    state: str = Field("unknown", description="État: 'libre', 'course_en_cours', 'course_prevue', 'unknown'")
    title: Optional[str] = Field(None, description="Nom du cours en cours")
    start_time: Optional[str] = Field(None, description="Heure de début (HH:MM)")
    end_time: Optional[str] = Field(None, description="Heure de fin (HH:MM)")
    professor: Optional[str] = Field(None, description="Nom du professeur")
    formation: Optional[str] = Field(None, description="Formations concernées")
    type: Optional[str] = Field(None, description="Type de cours (Cours, TP, Projet, etc.)")


class SystemStatus(BaseModel):
    """
    Statut complet du système SmartIGLab
    Réponse principale de l'API /status
    """
    occupied: bool = Field(..., description="Salle occupée (cours en cours ou prévu)")
    free_seats: int = Field(..., description="Places libres restantes")
    people_count: int = Field(..., description="Nombre de personnes détectées (vision)")
    capacity: int = Field(..., description="Capacité maximale de la salle")
    environment: EnvironmentData = Field(..., description="Données environnementales")
    hyperplanning: HyperplanningData = Field(..., description="État emploi du temps")
    vision_fps: float = Field(..., description="FPS du système de vision")
    updated_at: float = Field(..., description="Timestamp de la réponse")


class LoginRequest(BaseModel):
    """
    Données de connexion utilisateur
    """
    username: str = Field(..., description="Nom d'utilisateur")
    password: str = Field(..., description="Mot de passe")


class HealthResponse(BaseModel):
    """
    Réponse du endpoint /healthz
    Monitoring de l'état des services
    """
    status: str = Field(..., description="'ok' si tous les services fonctionnent")
    vision_running: bool = Field(..., description="Service vision YOLO actif")
    sensors_running: bool = Field(..., description="Service capteurs GPIO actif")
    uptime: float = Field(..., description="Temps depuis démarrage (secondes)")
