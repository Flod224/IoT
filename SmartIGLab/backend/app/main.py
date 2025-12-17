"""
SmartIGLab - Application Backend FastAPI
=========================================
API REST pour système IoT d'auditoire intelligent.

Architecture:
  - FastAPI avec lifespan management (démarrage/arrêt propre)
  - 3 services en threads: Vision YOLO, Capteurs GPIO, Hyperplanning
  - Rate limiting (60 req/min par IP) pour sécurité
  - CORS restreint (GET uniquement)
  - Authentification par clé API

Endpoints:
  GET /           - Info API
  GET /status     - Données complètes (authentifié)
  GET /healthz    - Health check (public)

Déploiement:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from collections import defaultdict
import threading

from app.config import settings
from app.models import SystemStatus, HealthResponse, EnvironmentData, HyperplanningData
from app.sensors import SensorReader
from app.hyperplanning import HyperplanningClient
from app.people_counter import PeopleCounter, Config as VisionConfig
import os

# === Configuration Logging ===
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === Services Globaux ===
# Partagés entre tous les endpoints (thread-safe)
vision_counter = None  # Compteur de personnes YOLO
sensor_reader = None  # Lecteur capteurs GPIO
hyperplanning_client = None  # Client emploi du temps
app_start_time = time.time()  # Timestamp démarrage pour uptime

# === Rate Limiting (Sécurité anti-DoS) ===
request_counts = defaultdict(list)  # {ip: [timestamp1, timestamp2, ...]}
rate_limit_lock = threading.Lock()  # Thread-safe
MAX_REQUESTS_PER_MINUTE = 60  # 1 requête/seconde maximum par IP


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie FastAPI
    
    Démarrage (avant yield):
      1. Initialise vision YOLO (si activée)
      2. Démarre capteurs GPIO (DHT22 + reed)
      3. Lance client Hyperplanning
    
    Arrêt (après yield):
      - Arrête proprement tous les threads
      - Libère ressources (caméra, GPIO)
    """
    global vision_counter, sensor_reader, hyperplanning_client
    
    logger.info("=== Démarrage SmartIGLab Backend ===")
    
    # 1. Module Vision YOLO
    if settings.vision_enabled:
        try:
            # Import dynamique du module vision
            vision_path = Path(__file__).parent.parent.parent / "vision"
            sys.path.insert(0, str(vision_path))
            
         
            
            # Chemin absolu vers le modèle YOLO local
            yolo_model_path = str(vision_path / settings.yolo_model)
            
            # Configurer via variables d'env
            os.environ["CAM_INDEX"] = str(settings.cam_index)
            os.environ["CAM_WIDTH"] = str(settings.cam_width)
            os.environ["CAM_HEIGHT"] = str(settings.cam_height)
            os.environ["YOLO_MODEL"] = yolo_model_path  # Chemin complet
            os.environ["YOLO_CONF"] = str(settings.yolo_conf)
            os.environ["YOLO_IMGSZ"] = str(settings.yolo_imgsz)
            os.environ["ROOM_CAPACITY"] = str(settings.room_capacity)
            os.environ["UPDATE_INTERVAL"] = str(settings.update_interval)
            os.environ["SHOW_VIDEO"] = "False"
            
            vision_config = VisionConfig()
            vision_counter = PeopleCounter(vision_config)
            vision_counter.start()
            logger.info("✓ Module vision YOLO démarré")
        except RuntimeError as e:
            logger.warning(f"⚠️  Module vision indisponible: {e}")
            logger.info("Le backend continuera sans détection de personnes (capteurs uniquement)")
            vision_counter = None
        except Exception as e:
            logger.error(f"✗ Erreur inattendue lors du démarrage vision: {e}", exc_info=True)
            logger.info("Le backend continuera sans détection de personnes (capteurs uniquement)")
            vision_counter = None
    else:
        logger.info("Module vision désactivé")
    
    # 2. Capteurs GPIO
    try:
        sensor_reader = SensorReader(
            dht_pin=settings.dht22_pin,
            reed_pin=settings.reed_switch_pin,
            interval=settings.sensor_read_interval
        )
        sensor_reader.start()
        logger.info(" Lecture capteurs GPIO démarrée")
    except Exception as e:
        logger.error(f" Erreur démarrage capteurs: {e}", exc_info=True)
        sensor_reader = None
    
    # 3. Client Hyperplanning
    if settings.hyperplanning_enabled:
        try:
            hyperplanning_client = HyperplanningClient(
                url=settings.hyperplanning_url,
                room_id=settings.hyperplanning_room_id,
                refresh_interval=settings.hyperplanning_refresh_interval
            )
            hyperplanning_client.start()
            logger.info("✓ Client Hyperplanning démarré")
        except Exception as e:
            logger.error(f"✗ Erreur démarrage Hyperplanning: {e}", exc_info=True)
            hyperplanning_client = None
    else:
        logger.info("Hyperplanning désactivé")
    
    logger.info("=== Backend prêt ===")
    
    yield  # L'app tourne ici
    
    # Nettoyage
    logger.info("=== Arrêt du backend ===")
    
    if vision_counter:
        vision_counter.stop()
    
    if sensor_reader:
        sensor_reader.stop()
    
    if hyperplanning_client:
        hyperplanning_client.stop()
    
    logger.info("=== Arrêt terminé ===")


# Création de l'app FastAPI
app = FastAPI(
    title="SmartIGLab API",
    description="API pour le système IoT SmartIGLab - auditoire IGLab",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware rate limiting (cybersec)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware de rate limiting (sécurité anti-DoS)
    
    Limite: 60 requêtes par minute par IP.
    Retourne HTTP 429 si dépassé.
    
    Thread-safe avec lock pour accès concurrent.
    """
    client_ip = request.client.host
    current_time = time.time()
    
    with rate_limit_lock:
        # Nettoyer les anciennes entrées (> 1 minute)
        request_counts[client_ip] = [t for t in request_counts[client_ip] if current_time - t < 60]
        
        # Vérifier limite
        if len(request_counts[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
            logger.warning(f"Rate limit dépassé pour {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."}
            )
        
        # Enregistrer requête
        request_counts[client_ip].append(current_time)
    
    response = await call_next(request)
    return response

# CORS
cors_origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],  # Seulement GET (lecture seule)
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    """
    Page d'accueil de l'API
    
    Retourne infos basiques sans authentification.
    """
    return {
        "name": "SmartIGLab API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/status", response_model=SystemStatus)
async def get_status(api_key: str = None):
    """
    Endpoint principal: état complet du système
    
    Sécurité:
      - Authentification par clé API (query param)
      - HTTP 403 si clé invalide ou absente
    
    Données retournées:
      - people_count: Nombre de personnes détectées (YOLO)
      - environment: Température, humidité, fenêtre (GPIO)
      - hyperplanning: État cours (iCal/JSON)
      - occupied: Salle occupée SI cours en cours (ignore people_count)
      - free_seats: Places libres (capacity - people_count)
    
    Logique occupation:
      OCCUPÉE = hyperplanning.state in ["course_en_cours", "course_prevue"]
      (Le nombre de personnes n'affecte PAS le statut)
    """
    # Vérification clé API
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    # Données vision
    people_count = 0
    fps = 0.0
    if vision_counter:
        people_count = vision_counter.people_count
        fps = vision_counter.fps
    
    # Données capteurs
    env_data = EnvironmentData(
        temperature=None,
        humidity=None,
        window_open=None,
        last_update=None
    )
    if sensor_reader:
        sensor_data = sensor_reader.get_data()
        env_data = EnvironmentData(
            temperature=sensor_data["temperature"],
            humidity=sensor_data["humidity"],
            window_open=sensor_data["window_open"],
            last_update=sensor_data["last_update"]
        )
    
    # Données Hyperplanning
    hp_data = HyperplanningData(state="unknown")
    if hyperplanning_client:
        hp_status = hyperplanning_client.get_status()
        hp_data = HyperplanningData(
            state=hp_status["state"],
            title=hp_status["title"],
            start_time=hp_status["start_time"],
            end_time=hp_status["end_time"],
            professor=hp_status["professor"]
        )
    
    # Calcul occupation
    free_seats = max(0, settings.room_capacity - people_count)
    
    # Règle occupation:
    # Salle LIBRE = pas de cours en hyperplanning (peu importe le nombre de personnes)
    # Salle OCCUPÉE = cours en cours selon hyperplanning
    occupied = False
    if hp_data.state in ["course_en_cours", "course_prevue"]:
        occupied = True
    # Note: on ignore people_count pour la détermination d'occupation
    
    return SystemStatus(
        occupied=occupied,
        free_seats=free_seats,
        people_count=people_count,
        capacity=settings.room_capacity,
        environment=env_data,
        hyperplanning=hp_data,
        vision_fps=fps,
        updated_at=time.time()
    )


@app.get("/healthz", response_model=HealthResponse)
async def healthcheck():
    """
    Endpoint de health check (monitoring)
    
    Accessible sans authentification.
    Utile pour supervision externe (Nagios, Prometheus, etc.).
    
    Returns:
      - status: "healthy" si au moins un service tourne
      - vision_running: Système vision actif
      - sensors_running: Capteurs GPIO actifs
      - uptime: Secondes depuis démarrage
    """
    vision_ok = vision_counter is not None and vision_counter._running if vision_counter else False
    sensors_ok = sensor_reader is not None and sensor_reader._running if sensor_reader else False
    
    uptime = time.time() - app_start_time
    
    return HealthResponse(
        status="healthy" if (vision_ok or sensors_ok) else "degraded",
        vision_running=vision_ok,
        sensors_running=sensors_ok,
        uptime=uptime
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Gestionnaire d'erreurs global (sécurité)
    
    Log l'erreur complète côté serveur mais retourne
    un message générique au client (pas de disclosure).
    """
    logger.error(f"Erreur non gérée: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur"}
    )
