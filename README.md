# SmartIGLab

Système IoT d'auditoire intelligent avec backend Raspberry Pi, DHT22, USB Caméra, yolov8n, Node-RED.

## Connexion SSH à la Raspberry Pi


**Note :** La connexion est possible uniquement via clé public ssh.

```bash
# Sur votre machine locale
ssh-keygen -t ed25519 -f ~/.ssh/smartiglab_key -C "smartiglab@<IP_RASPBERRY>"
```

**Copier la clé publique sur la Raspberry Pi:**

```bash
ssh-copy-id -i ~/.ssh/smartiglab_key.pub smartiglab@<IP_RASPBERRY>
mot_de_passe: smartwimiiglabflod32 # à modifier 

#Se connecter
ssh smartiglab@<IP_RASPBERRY>
```

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
nano app/.env  # Configurer identifiants admin, API key et rétention données

# Lancer le script
chmod +x start_https.sh
./start_https.sh
# Choisir: 1=JSON (démo) ou 2=ICS (calendrier réel)
```

**Variables d'environnement requises (.env):**
- `DASHBOARD_USERNAME` et `DASHBOARD_PASSWORD` : Utilisateur simple (accès dashboard uniquement)
- `ADMIN_USERNAME` et `ADMIN_PASSWORD` : Administrateur (accès interface admin + dashboard)
- `API_KEY` : Clé pour Node-RED (identique dans les deux configs)
- `DB_RETENTION_DAYS` : Nombre de jours de conservation des données historiques (défaut: 30)


## Architecture

```
Raspberry Pi (Backend)
  ├─ YOLO vision (caméra USB)
  ├─ Capteurs GPIO (DHT22)
  ├─ Hyperplanning (ICS/JSON)
  ├─ SQLite (historique capteurs avec rétention configurable)
  └─ API FastAPI :8000 (https)
  └─ Node-RED
```

## Interface Admin

Accès via `https://<IP_RASPBERRY>:8000/login` avec credentials admin

Fonctionnalités:
- Upload fichier ICS Hyperplanning
- Visualisation historique température/humidité
- Configuration rétention des données (1-365 jours)
- Nettoyage manuel des anciennes données
- Accès au dashboard via bouton dédié

## Authentification

Deux niveaux d'accès:
- **Utilisateur simple** : Accès dashboard uniquement (consultation)
- **Administrateur** : Accès interface admin + dashboard (configuration complète)

## Node-RED (Alertes email)

Installer node-red: `https://nodered.org/docs/getting-started/raspberrypi`
Installer `node-red-node-email>5.0.4`
Import du flow: `nodered/SmartIGLab_email_notif.json` + Deploiement
Injecter une seule fois le timestamp

**Fonctionnalités:**
- Lecture auto toutes les 30s via `/api/status`
- Alerte email si température > 50°C
- Alerte email si fenêtre ouverte après 21h

**Configuration:**
- Nœud email: Gmail SMTP avec App Password
- Header API: `X-API-Key: "Clé API configurée dans .env"`

## Configuration écran tactile

### Désactiver la fonction tactile (via SSH)

```bash
sudo nano /boot/firmware/config.txt
# Ajouter à la fin:
disable_touchscreen=1

sudo reboot
```

### Réactiver le tactile

```bash
sudo nano /boot/firmware/config.txt
# Retirer: disable_touchscreen=1
sudo reboot
```
