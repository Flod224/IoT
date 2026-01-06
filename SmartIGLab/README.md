# SmartIGLab

Système IoT d'auditoire intelligent avec backend Raspberry Pi, DHT22 et Caméra + YOLO.

## Démarrage

```bash
# Cloner et installer
git clone ...
cd SmartIGLab/
python3 -m venv yolovenv
source yolovenv/bin/activate
pip install -r requirements.txt

# Configurer
cp app/.env.example app/.env
nano app/.env  #Mettre ici les identifiants de connexion

# Lancer le script
chmod +x start_https.sh
./start_https.sh
# Choisir: 1=JSON (démo) ou 2=ICS (calendrier réel)
```

**Sources Hyperplanning:**
- **JSON** (`schedule_mock.json`) : Données de démo modifiables
- **ICS** (`Edt_Ho_IGLab.ics`) : Calendrier réel du local

## Architecture

```
Raspberry Pi (Backend)
  ├─ YOLO vision (caméra USB)
  ├─ Capteurs GPIO (DHT22)
  ├─ Hyperplanning (iCal/JSON)
  └─ API FastAPI :8000
```

## Configuration écran tactile

### Désactiver la fonction tactile (via SSH)

```bash
sudo nano /boot/firmware/config.txt
# Ajouter à la fin du fichier :
disable_touchscreen=1

# Redémarrer
sudo reboot
```

### Réactiver le tactile

```bash
sudo nano /boot/firmware/config.txt
# Retirer: disable_touchscreen=1
sudo reboot
```
