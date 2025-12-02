# SmartIGLab Backend

Backend unifié FastAPI intégrant:
- **Vision YOLO** (comptage personnes)
- **Capteurs GPIO** (DHT22 température/humidité + reed switch fenêtre)
- **Hyperplanning** (état des cours)
- **API REST** pour consultation externe

## Installation sur Raspberry Pi

### Prérequis système
```bash
sudo apt update
sudo apt install -y python3-pip python3-dev python3-venv
sudo apt install -y libgpiod2 python3-libgpiod  # Pour GPIO
```

### Setup projet
```bash
cd ~/IoT/backend

# Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer dépendances
pip install -r requirements.txt

# Si sur Raspberry Pi (GPIO):
pip install RPi.GPIO adafruit-circuitpython-dht

# Configuration
cp .env.example .env
nano .env  # Ajuster selon votre setup
```

### Configuration `.env`
Paramètres principaux à vérifier:
- `ROOM_CAPACITY`: capacité de la salle
- `DHT22_PIN`: pin GPIO pour DHT22 (défaut: 4)
- `REED_SWITCH_PIN`: pin GPIO pour reed (défaut: 17)
- `VISION_ENABLED`: True si caméra disponible
- `HYPERPLANNING_ENABLED`: True quand API configurée

## Lancement

### Mode développement
```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Mode production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### Service systemd
```bash
sudo nano /etc/systemd/system/smartiglab-backend.service
```

Contenu:
```ini
[Unit]
Description=SmartIGLab Backend API
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/IoT/backend
Environment="PATH=/home/pi/IoT/backend/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/pi/IoT/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activation:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smartiglab-backend.service
sudo systemctl start smartiglab-backend.service
sudo systemctl status smartiglab-backend.service
```

Logs:
```bash
sudo journalctl -u smartiglab-backend.service -f
```

## API Endpoints

### `GET /status`
Statut complet du système.

**Réponse:**
```json
{
  "occupied": true,
  "free_seats": 28,
  "people_count": 12,
  "capacity": 40,
  "environment": {
    "temperature": 22.5,
    "humidity": 45.2,
    "window_open": false,
    "last_update": 1733155234.56
  },
  "hyperplanning": {
    "state": "course_en_cours",
    "title": "Cours IoT - MA2",
    "start_time": "14:00",
    "end_time": "17:00"
  },
  "vision_fps": 6.3,
  "updated_at": 1733155234.56
}
```

### `GET /healthz`
Health check.

**Réponse:**
```json
{
  "status": "healthy",
  "vision_running": true,
  "sensors_running": true,
  "uptime": 3600.5
}
```

### `GET /metrics`
Métriques détaillées pour monitoring.

### `GET /docs`
Documentation interactive (Swagger UI).

## Architecture

```
Backend (FastAPI)
├── Vision Module (thread)
│   └── YOLO people counter → people_count
├── Sensor Reader (thread)
│   ├── DHT22 → temperature, humidity
│   └── Reed switch → window_open
├── Hyperplanning Client (thread)
│   └── API polling → course state
└── REST API
    ├── GET /status (agrégation)
    ├── GET /healthz
    └── GET /metrics
```

Chaque module tourne en thread background et expose son état via propriétés thread-safe.

## GPIO Wiring

### DHT22 (par défaut GPIO 4)
- VCC → 3V3 (pin 1)
- GND → GND (pin 6)
- DATA → GPIO 4 (pin 7) + résistance 4.7kΩ vers 3V3

### Reed Switch (par défaut GPIO 17)
- Un côté → GPIO 17 (pin 11) avec `INPUT_PULLUP`
- Autre côté → GND (pin 9)
- État: circuit ouvert = fenêtre ouverte (HIGH)

Schéma détaillé: voir `docs/hardware.md`

## Test sans Raspberry Pi

Le backend peut tourner sur une machine de développement (Windows/Linux/Mac):
- Vision simulée si pas de caméra
- Capteurs GPIO simulés (données aléatoires)
- Hyperplanning en mode mock

```bash
# Sur PC de dev
pip install -r requirements.txt
# Éditer .env: VISION_ENABLED=False
uvicorn app.main:app --reload
# Accéder à http://localhost:8000/docs
```

## Sécurité

- CORS configuré via `CORS_ORIGINS` (défaut: `*` pour dev)
- Déploiement derrière reverse proxy (Caddy/Nginx) recommandé pour HTTPS
- Authentification admin à ajouter pour endpoints futurs `/admin/*`

## Troubleshooting

### Erreur GPIO
```bash
# Vérifier permissions
sudo usermod -aG gpio pi
# Relancer session

# Tester DHT22
python3 -c "import adafruit_dht; import board; dht = adafruit_dht.DHT22(board.D4); print(dht.temperature)"
```

### Vision ne démarre pas
```bash
# Vérifier module vision installé
cd ~/IoT/vision
pip install -r requirements.txt

# Tester isolation
python3 people_counter.py
```

### Port déjà utilisé
```bash
# Changer port dans .env: PORT=8001
# Ou tuer processus
sudo lsof -ti:8000 | xargs sudo kill -9
```
