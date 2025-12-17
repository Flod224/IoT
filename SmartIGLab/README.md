# SmartIGLab

Système IoT d'auditoire intelligent avec backend Raspberry Pi + dashboard ESP32.

##  Démarrage rapide

### 1. Backend (Raspberry Pi)

```bash
cloner le repo
cd SmartIGLab/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurer
cp app/.env.example app/.env
nano app/.env  # Éditer API_KEY, pins GPIO, etc.

# Lancer
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. ESP32 (Arduino IDE)

```bash
cd firmware/esp32-webserver/esp32_webserver
cp config.h.example config.h
nano config.h  # WiFi + API_URL + API_KEY
```

Puis :
1. Ouvrir `esp32_webserver.ino` dans Arduino IDE
2. Board : ESP32 Dev Module
3. Upload

## Fichiers à configurer

| Fichier | Contenu |
|---------|---------|
| `backend/app/.env` | API_KEY, GPIO pins, capacité salle |
| `firmware/esp32-webserver/esp32_webserver/config.h` | WiFi, API_URL, API_KEY |

**Important** : Les `API_KEY` doivent être identiques dans les 2 fichiers.

## Architecture

```
Raspberry Pi (Backend)
  ├─ YOLO vision (caméra USB)
  ├─ Capteurs GPIO (DHT22, reed switch)
  ├─ Hyperplanning (iCal/JSON)
  └─ API FastAPI :8000

ESP32 (Dashboard)
  ├─ Connexion WiFi
  ├─ Fetch API backend
  └─ Serveur web :80
```

## Dépendances

**Backend** :
```bash
sudo apt-get install python3-rpi.gpio python3-dev
pip install -r backend/requirements.txt
```

**ESP32** :
- Arduino IDE avec ESP32 core
- Bibliothèque : ArduinoJson

## Générer clé API

```bash
openssl rand -hex 64
```

Copier la clé dans `backend/app/.env` ET `firmware/.../config.h`
