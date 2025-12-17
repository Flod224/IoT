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

## Fichiers à configurer

| Fichier | Contenu |
|---------|---------|
| `backend/app/.env` |GPIO pins, capacité salle | Identifiants de connexion


## Architecture

```
Raspberry Pi (Backend)
  ├─ YOLO vision (caméra USB)
  ├─ Capteurs GPIO (DHT22)
  ├─ Hyperplanning (iCal/JSON)
  └─ API FastAPI :8000


## Dépendances

**Backend** :
```bash
sudo apt-get install python3-rpi.gpio python3-dev
pip install -r backend/requirements.txt
```

