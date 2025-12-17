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

## 🖥️ Configuration écran tactile

### Désactiver la fonction tactile (via SSH)

Si vous utilisez un écran tactile mais souhaitez désactiver le tactile :

```bash
# 1. Identifier le périphérique tactile
xinput list

# 2. Désactiver le tactile (remplacer <ID> par l'ID du périphérique)
xinput disable <ID>

# Exemple si l'ID est 6:
xinput disable 6
```

**Méthode alternative (permanent au redémarrage) :**

```bash
# Créer fichier de configuration
sudo nano /etc/X11/xorg.conf.d/99-no-touchscreen.conf
```

Ajouter ce contenu :
```
Section "InputClass"
    Identifier "Disable Touchscreen"
    MatchIsTouchscreen "on"
    Option "Ignore" "on"
EndSection
```

Puis redémarrer :
```bash
sudo reboot
```

### Réactiver le tactile

```bash
# Réactiver temporairement
xinput enable <ID>

# Réactiver définitivement
sudo rm /etc/X11/xorg.conf.d/99-no-touchscreen.conf
sudo reboot
```

