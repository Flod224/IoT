"""
Application principale FastAPI - SmartIGLab Backend
Intègre: vision YOLO + capteurs GPIO + Hyperplanning + API
"""

import sys
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import SystemStatus, HealthResponse, EnvironmentData, HyperplanningData
from app.sensors import SensorReader
from app.hyperplanning import HyperplanningClient

# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables globales pour les services
vision_counter = None
sensor_reader = None
hyperplanning_client = None
app_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    global vision_counter, sensor_reader, hyperplanning_client
    
    logger.info("=== Démarrage SmartIGLab Backend ===")
    
    # 1. Module Vision YOLO
    if settings.vision_enabled:
        try:
            # Import dynamique du module vision
            vision_path = Path(__file__).parent.parent.parent / "vision"
            sys.path.insert(0, str(vision_path))
            
            from people_counter import PeopleCounter, Config as VisionConfig
            import os
            
            # Configurer via variables d'env
            os.environ["CAM_INDEX"] = str(settings.cam_index)
            os.environ["CAM_WIDTH"] = str(settings.cam_width)
            os.environ["CAM_HEIGHT"] = str(settings.cam_height)
            os.environ["YOLO_MODEL"] = settings.yolo_model
            os.environ["YOLO_CONF"] = str(settings.yolo_conf)
            os.environ["YOLO_IMGSZ"] = str(settings.yolo_imgsz)
            os.environ["ROOM_CAPACITY"] = str(settings.room_capacity)
            os.environ["UPDATE_INTERVAL"] = str(settings.update_interval)
            os.environ["SHOW_VIDEO"] = "False"
            
            vision_config = VisionConfig()
            vision_counter = PeopleCounter(vision_config)
            vision_counter.start()
            logger.info("✓ Module vision YOLO démarré")
        except Exception as e:
            logger.error(f"✗ Erreur démarrage vision: {e}", exc_info=True)
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

# CORS
cors_origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    """Page d'accueil"""
    return {
        "name": "SmartIGLab API",
        "version": "1.0.0",
        "endpoints": {
            "status": "/status",
            "health": "/healthz",
            "docs": "/docs"
        }
    }


@app.get("/status", response_model=SystemStatus)
async def get_status():
    """
    Retourne l'état complet du système
    
    Combine:
    - Comptage personnes (YOLO)
    - Données environnementales (DHT22 + reed)
    - État Hyperplanning
    """
    
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
            end_time=hp_status["end_time"]
        )
    
    # Calcul occupation
    free_seats = max(0, settings.room_capacity - people_count)
    
    # Règle occupation:
    # - Si cours en cours/prévu selon Hyperplanning → occupé
    # - Sinon basé sur détection (> 0 personnes)
    occupied = False
    if hp_data.state in ["course_en_cours", "course_prevue"]:
        occupied = True
    elif people_count > 0:
        occupied = True
    
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
    Health check pour monitoring
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


@app.get("/metrics")
async def metrics():
    """
    Métriques détaillées pour monitoring
    """
    vision_status = vision_counter.get_status() if vision_counter else {}
    sensor_data = sensor_reader.get_data() if sensor_reader else {}
    hp_status = hyperplanning_client.get_status() if hyperplanning_client else {}
    
    return {
        "vision": vision_status,
        "sensors": sensor_data,
        "hyperplanning": hp_status,
        "uptime": time.time() - app_start_time,
        "config": {
            "capacity": settings.room_capacity,
            "vision_enabled": settings.vision_enabled,
            "hyperplanning_enabled": settings.hyperplanning_enabled
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handler global pour les exceptions"""
    logger.error(f"Erreur non gérée: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur"}
    )
