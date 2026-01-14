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

Déploiement:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends, Cookie, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, RedirectResponse
from collections import defaultdict
import threading
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import shutil

from app.config import settings
from app.models import SystemStatus, HealthResponse, EnvironmentData, HyperplanningData, LoginRequest
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

# === Gestion Sessions (dictionnaire en mémoire) ===
# En production: utiliser Redis ou base de données
active_sessions = {}  # {session_token: {username, expires_at}}
sessions_lock = threading.Lock()
SESSION_DURATION = timedelta(hours=24)  # Durée validité session

# === Rate Limiting (Sécurité anti-DoS) ===
request_counts = defaultdict(list)  # {ip: [timestamp1, timestamp2, ...]}
rate_limit_lock = threading.Lock()  # Thread-safe
MAX_REQUESTS_PER_MINUTE = 60  # 1 requête/seconde maximum par IP


def create_session_token(username: str) -> str:
    """Génère un token de session sécurisé"""
    random_data = secrets.token_bytes(32)
    timestamp = str(datetime.now().timestamp()).encode()
    combined = username.encode() + random_data + timestamp
    return hashlib.sha256(combined).hexdigest()


def verify_session(session_token: Optional[str] = Cookie(None)):
    """
    Vérifie la validité de la session via cookie
    
    Retourne (username, role) si valide, sinon lève 401.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    
    with sessions_lock:
        session = active_sessions.get(session_token)
        
        if not session:
            raise HTTPException(status_code=401, detail="Session invalide")
        
        # Vérifier expiration
        if datetime.now() > session['expires_at']:
            del active_sessions[session_token]
            raise HTTPException(status_code=401, detail="Session expirée")
        
        return session['username'], session.get('role', 'user')


def verify_admin_session(session_token: Optional[str] = Cookie(None)):
    """
    Vérifie que la session est valide ET que l'utilisateur est admin
    
    Retourne (username, role) si admin, sinon lève 403.
    """
    username, role = verify_session(session_token)
    
    if role != 'admin':
        raise HTTPException(status_code=403, detail="Accès admin requis")
    
    return username, role


def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Vérifie la clé API pour les services internes (Node-RED)
    
    Header attendu: X-API-Key: <votre_clé>
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key manquante")
    
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="API Key invalide")
    
    return True


def cleanup_expired_sessions():
    """Nettoie les sessions expirées (appelé périodiquement)"""
    with sessions_lock:
        now = datetime.now()
        expired = [token for token, data in active_sessions.items() if now > data['expires_at']]
        for token in expired:
            del active_sessions[token]
        if expired:
            logger.info(f"Nettoyage: {len(expired)} session(s) expirée(s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie FastAPI
    
    Démarrage (avant yield):
      1. Initialise la base de données SQLite
      2. Initialise vision YOLO (si activée)
      3. Démarre capteurs GPIO (DHT22 + reed)
      4. Lance client Hyperplanning
    
    Arrêt (après yield):
      - Arrête proprement tous les threads
      - Libère ressources (caméra, GPIO)
    """
    global vision_counter, sensor_reader, hyperplanning_client
    
    logger.info("=== Démarrage SmartIGLab Backend ===")
    
    # 0. Initialiser la base de données
    try:
        from app.database import init_database
        init_database()
    except Exception as e:
        logger.error(f"✗ Erreur initialisation base de données: {e}")
    
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
                use_ics=settings.hyperplanning_use_ics,
                refresh_interval=settings.hyperplanning_refresh_interval
            )
            hyperplanning_client.start()
            source = "ICS" if settings.hyperplanning_use_ics else "JSON"
            logger.info(f"✓ Client Hyperplanning démarré ({source})")
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
    allow_methods=["GET", "POST"],  # GET + POST pour login/logout
    allow_headers=["*"],
)


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page():
    """
    Page de connexion
    """
    html_path = Path(__file__).parent.parent.parent / "frontend" / "login.html"
    
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Page de login non trouvée")
    
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/login", include_in_schema=False)
async def login(credentials: LoginRequest):
    """
    Authentification utilisateur (user simple ou admin)
    
    Vérifie credentials et crée session avec rôle approprié.
    Retourne cookie de session.
    """
    role = None
    
    # Vérifier si c'est un admin
    is_admin = (
        secrets.compare_digest(credentials.username, settings.admin_username) and
        secrets.compare_digest(credentials.password, settings.admin_password)
    )
    
    if is_admin:
        role = 'admin'
    else:
        # Vérifier si c'est un user simple
        is_user = (
            secrets.compare_digest(credentials.username, settings.dashboard_username) and
            secrets.compare_digest(credentials.password, settings.dashboard_password)
        )
        
        if is_user:
            role = 'user'
    
    if not role:
        return JSONResponse(
            status_code=401,
            content={"success": False, "detail": "Identifiants invalides"}
        )
    
    # Créer session avec rôle
    session_token = create_session_token(credentials.username)
    expires_at = datetime.now() + SESSION_DURATION
    
    with sessions_lock:
        active_sessions[session_token] = {
            'username': credentials.username,
            'role': role,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
    
    logger.info(f"Nouvelle session pour {credentials.username} (rôle: {role})")
    
    # Retourner réponse avec cookie
    response = JSONResponse(content={"success": True})
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,  # Protection XSS
        secure=True,  # Cookie uniquement sur HTTPS
        samesite="lax",  # Protection CSRF
        max_age=int(SESSION_DURATION.total_seconds())
    )
    
    return response


@app.post("/logout", include_in_schema=False)
async def logout(session_token: Optional[str] = Cookie(None)):
    """
    Déconnexion utilisateur
    
    Supprime la session et le cookie.
    """
    if session_token:
        with sessions_lock:
            if session_token in active_sessions:
                username = active_sessions[session_token]['username']
                del active_sessions[session_token]
                logger.info(f"Déconnexion: {username}")
    
    # Supprimer cookie
    response = JSONResponse(content={"success": True})
    response.delete_cookie(key="session_token")
    
    return response


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(session_token: Optional[str] = Cookie(None)):
    """Page d'administration (réservée aux admins uniquement)"""
    try:
        verify_admin_session(session_token)  # Vérifier rôle admin
        cleanup_expired_sessions()
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)
    
    html_path = Path(__file__).parent.parent.parent / "frontend" / "admin.html"
    
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Page admin non trouvée")
    
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/admin/upload-ics", include_in_schema=False)
async def upload_ics(file: UploadFile = File(...), session_token: Optional[str] = Cookie(None)):
    """Upload fichier .ICS pour hyperplanning"""
    # Vérifier session admin
    verify_admin_session(session_token)
    
    # Vérifier extension
    if not file.filename.endswith('.ics'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format .ICS")
    
    try:
        # Sauvegarder le fichier
        ics_path = Path(__file__).parent.parent / "Edt_Ho_IGLab.ics"
        
        with open(ics_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        logger.info(f"Fichier ICS uploadé: {file.filename}")
        
        # Redémarrer hyperplanning client si actif
        if hyperplanning_client:
            hyperplanning_client.stop()
            hyperplanning_client.start()
            logger.info("Client Hyperplanning redémarré avec nouveau fichier")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Fichier {file.filename} uploadé avec succès"
        })
        
    except Exception as e:
        logger.error(f"Erreur upload ICS: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'upload: {str(e)}")


@app.get("/admin/history", include_in_schema=False)
async def get_history(hours: int = 24, session_token: Optional[str] = Cookie(None)):
    """Récupère l'historique des capteurs"""
    # Vérifier session admin
    verify_admin_session(session_token)
    
    try:
        from app.database import get_sensor_history
        history = get_sensor_history(hours=hours)
        
        return JSONResponse(content={
            "success": True,
            "data": history,
            "count": len(history)
        })
        
    except Exception as e:
        logger.error(f"Erreur récupération historique: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.get("/admin/config", include_in_schema=False)
async def get_config(session_token: Optional[str] = Cookie(None)):
    """Récupère la configuration actuelle de rétention des données"""
    verify_admin_session(session_token)
    
    return JSONResponse(content={
        "success": True,
        "db_retention_days": settings.db_retention_days
    })


@app.post("/admin/config", include_in_schema=False)
async def update_config(retention_days: int, session_token: Optional[str] = Cookie(None)):
    """Met à jour la configuration de rétention des données"""
    verify_admin_session(session_token)
    
    if retention_days < 1 or retention_days > 365:
        raise HTTPException(status_code=400, detail="Le nombre de jours doit être entre 1 et 365")
    
    try:
        # Mettre à jour la config en mémoire
        settings.db_retention_days = retention_days
        
        # Mettre à jour le fichier .env
        env_path = Path(__file__).parent / ".env"
        lines = []
        found = False
        
        if env_path.exists():
            with open(env_path, "r") as f:
                lines = f.readlines()
            
            # Chercher et modifier la ligne DB_RETENTION_DAYS
            for i, line in enumerate(lines):
                if line.strip().startswith("DB_RETENTION_DAYS="):
                    lines[i] = f"DB_RETENTION_DAYS={retention_days}\n"
                    found = True
                    break
        
        # Si pas trouvé, ajouter à la fin
        if not found:
            lines.append(f"\n# === BASE DE DONNÉES ===\n")
            lines.append(f"DB_RETENTION_DAYS={retention_days}\n")
        
        # Écrire le fichier
        with open(env_path, "w") as f:
            f.writelines(lines)
        
        logger.info(f"Configuration mise à jour: rétention={retention_days} jours")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Rétention mise à jour: {retention_days} jours"
        })
        
    except Exception as e:
        logger.error(f"Erreur mise à jour config: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.post("/admin/cleanup", include_in_schema=False)
async def trigger_cleanup(session_token: Optional[str] = Cookie(None)):
    """Déclenche manuellement le nettoyage des vieilles données"""
    verify_admin_session(session_token)
    
    try:
        from app.database import cleanup_old_data
        cleanup_old_data(days=settings.db_retention_days)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Nettoyage effectué (données > {settings.db_retention_days} jours)"
        })
        
    except Exception as e:
        logger.error(f"Erreur nettoyage: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.get("/user/info", include_in_schema=False)
async def get_user_info(session_token: Optional[str] = Cookie(None)):
    """
    Retourne les informations de l'utilisateur courant
    (username, rôle)
    """
    try:
        username, role = verify_session(session_token)
        return JSONResponse(content={
            "success": True,
            "username": username,
            "role": role
        })
    except HTTPException:
        raise HTTPException(status_code=401, detail="Non authentifié")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(session_token: Optional[str] = Cookie(None)):
    """
    Dashboard web principal
    
    Sécurité: Session cookie
    Redirige vers /login si non authentifié
    """
    # Vérifier session
    try:
        username = verify_session(session_token)
        cleanup_expired_sessions()  # Nettoyage périodique
    except HTTPException:
        # Non authentifié -> redirection login
        return RedirectResponse(url="/login", status_code=302)
    
    # Servir dashboard
    html_path = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard non trouvé")
    
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/status", response_model=SystemStatus)
async def get_status(session_token: Optional[str] = Cookie(None)):
    """
    Endpoint principal: état complet du système
    
    Sécurité:
      - Authentification par session cookie
      - HTTP 401 si session invalide
    
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
    # Vérifier session
    verify_session(session_token)
    
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
        window_open=False,  # Défaut: fermée
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
            professor=hp_status["professor"],
            formation=hp_status.get("formation"),
            type=hp_status.get("type")
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


@app.get("/api/status", response_model=SystemStatus)
async def get_status_api(api_key_valid: bool = Depends(verify_api_key)):
    """
    Endpoint API pour services internes (Node-RED, monitoring)
    
    Sécurité:
      - Authentification par API Key (header X-API-Key)
      - Pas de cookie nécessaire
    
    Usage:
      curl -H "X-API-Key: votre_clé" https://localhost:8000/api/status
    """
    # Même logique que /status mais sans cookie
    people_count = 0
    fps = 0.0
    if vision_counter:
        people_count = vision_counter.people_count
        fps = vision_counter.fps
    
    env_data = EnvironmentData(
        temperature=None,
        humidity=None,
        window_open=False,  # Défaut: fermée
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
    
    hp_data = HyperplanningData(state="unknown")
    if hyperplanning_client:
        hp_status = hyperplanning_client.get_status()
        hp_data = HyperplanningData(
            state=hp_status["state"],
            title=hp_status["title"],
            start_time=hp_status["start_time"],
            end_time=hp_status["end_time"],
            professor=hp_status["professor"],
            formation=hp_status.get("formation"),
            type=hp_status.get("type")
        )
    
    free_seats = max(0, settings.room_capacity - people_count)
    occupied = False
    if hp_data.state in ["course_en_cours", "course_prevue"]:
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
