# Journal de Projet IoT

Ce fichier documente en continu les actions, commandes, décisions et résultats liés au projet. Ajoute une nouvelle section par jour avec date et objectifs.

---

## 2025-11-27 — Mise en route du Raspberry Pi

- Objectif du jour: Préparer le Raspberry Pi et établir la connexion SSH sur le même réseau via le hostname.
- Actions réalisées:
  - Image installée sur la carte SD avec Raspberry Pi Imager
  - Wi‑Fi configuré dans l’outil (SSID/Mot de passe)
  - SSH activé (via options avancées de l’imager)

### Connexion SSH depuis Windows (PowerShell)

Remplacer `<utilisateur>` et `<hostname>` par vos valeurs (ex: `pi` et `raspberrypi`). Si vous avez défini un utilisateur personnalisé dans Raspberry Pi Imager, utilisez celui‑là.

Vérifier que le port SSH (22) répond:

```powershell
Test-NetConnection -ComputerName raspberrypi.local -Port 22
```

Connexion via le hostname (mDNS `.local`):

```powershell
ssh <utilisateur>@<hostname>.local
# Exemple
ssh pi@raspberrypi.local
```

Notes:
- Au premier accès, répondre `yes` à l’empreinte (host key).
- Après connexion, changer le mot de passe si besoin:

```bash
passwd
```

### Dépannage rapide (optionnel)

- Tester la résolution et la latence:

```powershell
ping raspberrypi.local
```

- Vérifier l’ouverture du port 22:

```powershell
Test-NetConnection -ComputerName raspberrypi.local -Port 22
```

- Si `raspberrypi.local` ne se résout pas:
  - S’assurer que le PC et le Pi sont sur le même réseau.
  - Réessayer avec le hostname exact défini dans l’imager: `ssh <utilisateur>@<votre-hostname>.local`.
  - En dernier recours, utiliser l’adresse IP du Pi: `ssh <utilisateur>@<IP_du_Pi>` (trouvable via votre routeur/box).

### Prochaines étapes
- Installer mises à jour et paquets de base sur le Pi.
- Configurer la synchronisation de l’heure et paramètres régionaux.
- Déployer les premiers scripts/services du projet.

---

## Notes diverses
- Ajouter ici toute décision d’architecture, versions logicielles, références, liens utiles, etc.

---

## 2025-11-27 — Découverte du réseau local (scan IP)

- Objectif: Lister les IP actives sur mon sous-réseau local depuis Windows.

### Méthode A — PowerShell natif (/24 classique)

1) Récupérer votre IP locale et déduire la base du réseau:

```powershell
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Select-Object -First 1).IPAddress
$parts = $ip.Split('.')
$base = "$($parts[0]).$($parts[1]).$($parts[2])"
"IP locale: $ip"; "Base réseau (présumée /24): $base.0/24"
```

2) Balayer la plage et afficher les hôtes qui répondent (plus rapide avec ping) :

```powershell
$live = @()
1..254 | ForEach-Object {
  $addr = "$base.$_"
  if (ping -n 1 -w 150 $addr | Select-String 'TTL=') {
    $live += $addr
    Write-Host $addr
  }
}
$live
```

3) Voir le tableau ARP (IP ↔ MAC) après le balayage:

```powershell
Get-NetNeighbor -AddressFamily IPv4 |
  Where-Object { $_.State -match 'Reachable|Stale' } |
  Sort-Object IPAddress |
  Format-Table IPAddress,LinkLayerAddress,State
```

Astuce: Certains équipements ne répondent pas au ping (ICMP). Même s’ils n’apparaissent pas dans `$live`, ils peuvent figurer dans l’ARP après d’autres trafics réseau.

### Méthode B — Nmap (si installé)

1) Identifier rapidement votre IP et le préfixe:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Select-Object IPAddress, PrefixLength
```

2) Lancer un ping sweep sur le sous-réseau (exemples):

```powershell
# Exemple pour 192.168.1.0/24
nmap -sn 192.168.1.0/24

# Exemple pour 10.0.0.0/24
nmap -sn 10.0.0.0/24
```

Notes:
- Adaptez la plage au préfixe affiché (souvent /24 en réseau domestique).
- Nmap offre un résultat plus rapide/précis, avec noms d’hôte quand disponibles.

### Résultats attendus
- Liste d’IP actives, éventuellement hostnames (si résolus) et adresses MAC via ARP.
- Utiliser ensuite ces IP pour SSH/HTTP/etc.

---

## 2025-11-27 — Intégration du module YOLO sur Raspberry Pi

- Objectif: Installer et intégrer un module de détection d’objets (YOLO) avec flux webcam et publication via serveur web.

### Choix du modèle et considérations de performance
- Options: YOLOv5/YOLOv8 (Ultralytics), variantes Nano/Small pour Pi; ou export ONNX/TensorRT (si Jetson, non applicable ici), ou NCNN (plus léger).
- Recommandation initiale: `yolov8n` (nano) pour démarrer; résolution 640x480 ou 320x240 pour latence réduite.
- Accélération: Sur Pi 4, privilégier CPU optimisé + OpenCV; Coral TPU (USB) optionnel si disponible.

### Pré-requis système (sur le Raspberry Pi via SSH)

```bash
# Mettre à jour le système
sudo apt update
sudo apt full-upgrade -y

# Paquets de base
sudo apt install -y python3 python3-pip python3-venv git ffmpeg libatlas-base-dev

# Optionnel: OpenCV depuis apt (suffisant pour capture basique)
sudo apt install -y python3-opencv

# Créer un environnement Python dédié au projet
python3 -m venv ~/iot-env
source ~/iot-env/bin/activate
pip install --upgrade pip wheel setuptools
```

### Installer Ultralytics (YOLOv8)

```bash
# Dans l'environnement virtuel
pip install ultralytics
# Pour webcam et traitements
pip install opencv-python
# Optionnel pour web API
pip install fastapi uvicorn[standard]
```

### Test rapide de détection avec webcam

```bash
python - << 'PY'
from ultralytics import YOLO
import cv2

model = YOLO('yolov8n.pt')
cap = cv2.VideoCapture(0)
if not cap.isOpened():
  raise RuntimeError('Webcam introuvable (VideoCapture(0)).')

while True:
  ok, frame = cap.read()
  if not ok:
    break
  results = model.predict(source=frame, imgsz=480, conf=0.5, verbose=False)
  annotated = results[0].plot()
  cv2.imshow('YOLOv8n', annotated)
  if cv2.waitKey(1) & 0xFF == 27: # ESC pour quitter
    break
cap.release()
cv2.destroyAllWindows()
PY
```

Si la fenêtre s’ouvre et montre des boxes, YOLO fonctionne.

### Intégration serveur web (Flux + API)

Option A — FastAPI avec MJPEG pour diffuser le flux annoté:

```bash
cat > app.py << 'PY'
from ultralytics import YOLO
import cv2
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import time

app = FastAPI()
model = YOLO('yolov8n.pt')
cap = cv2.VideoCapture(0)

if not cap.isOpened():
  raise RuntimeError('Webcam introuvable')

# Générateur MJPEG

def mjpeg_stream():
  while True:
    ok, frame = cap.read()
    if not ok:
      time.sleep(0.05)
      continue
    results = model.predict(source=frame, imgsz=480, conf=0.5, verbose=False)
    annotated = results[0].plot()
    _, jpg = cv2.imencode('.jpg', annotated)
    frame_bytes = jpg.tobytes()
    yield (b"--frame\r\n"
         b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

@app.get('/')
async def root():
  return {"status": "ok"}

@app.get('/video')
def video():
  return StreamingResponse(mjpeg_stream(), media_type='multipart/x-mixed-replace; boundary=frame')
PY

# Lancer le serveur (port 8000)
uvicorn app:app --host 0.0.0.0 --port 8000
```

Ensuite, ouvrir `http://<ip_du_pi>:8000/video` depuis le navigateur.

### Intégration des données capteurs et ESP32
- DHT22 (temp/humidité): lire via GPIO (lib `Adafruit_DHT` ou `gpiozero`), exposer `/sensors` dans FastAPI.
- Capteur ouverture/fermeture: GPIO avec pull-up/down, endpoint `/window_state`.
- ESP32: publier données vers le Pi (HTTP/MQTT). Côté Pi, récupérer et afficher sur page web (templates simples ou overlay texte sur vidéo).

Exemple endpoints FastAPI minimal pour capteurs:

```bash
pip install adafruit-circuitpython-dht gpiozero
cat >> app.py << 'PY'
from gpiozero import Button
import adafruit_dht
import board

# DHT22 sur pin GPIO4 (BCM)
dht_device = adafruit_dht.DHT22(board.D4)
# Capteur magnétique (reed) sur GPIO17 (BCM)
reed = Button(17, pull_up=True)

@app.get('/sensors')
def sensors():
  try:
    temp = dht_device.temperature
    hum = dht_device.humidity
  except Exception:
    temp = None; hum = None
  return {"temperature": temp, "humidity": hum}

@app.get('/window_state')
def window_state():
  return {"open": reed.is_pressed}
PY
```

### Bonnes pratiques
- Utiliser `python3 -m venv` pour isoler les dépendances.
- Limiter la résolution et `imgsz` pour performance.
- Journaliser CPU/RAM et FPS pour ajuster les paramètres.
- Démarrer `uvicorn` en service systemd pour disponibilité.

### Prochaines étapes
- Valider la capture webcam et le flux `/video`.
- Brancher et tester DHT22 + capteur ouverture.
- Définir le format des données envoyées par l’ESP32 (HTTP/MQTT) et les endpoints côté Pi.

