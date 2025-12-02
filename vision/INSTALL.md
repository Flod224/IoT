# Vision (Pi) – SmartIGLab

## Objectif
Comptage de personnes en temps réel (YOLOv8n) sur Raspberry Pi avec publication MQTT.

## Installation sur Raspberry Pi

### Prérequis
```bash
sudo apt update
sudo apt install -y python3-pip python3-opencv libopencv-dev
```

### Installation des dépendances Python
```bash
cd ~/IoT/vision
pip3 install -r requirements.txt
```

Le premier lancement téléchargera automatiquement le modèle YOLOv8n (~6 MB).

### Configuration
```bash
cp .env.example .env
nano .env
```

Paramètres à ajuster:
- `MQTT_HOST`: IP du broker MQTT (Pi ou autre)
- `MQTT_USER`/`MQTT_PASS`: si authentification activée
- `CAM_INDEX`: 0 pour webcam USB, vérifier avec `ls /dev/video*`
- `YOLO_CONF`: seuil de confiance (0.5 par défaut)
- `SHOW_VIDEO`: True pour affichage local debug (nécessite X11)

### Vérification caméra
```bash
# Lister caméras disponibles
ls -l /dev/video*

# Test rapide avec fswebcam
sudo apt install fswebcam
fswebcam -d /dev/video0 test.jpg
```

## Lancement

### Mode production (sans affichage)
```bash
python3 people_counter.py
```

### Mode debug (avec affichage vidéo)
```bash
# Modifier .env: SHOW_VIDEO=True
python3 people_counter.py
# Appuyer sur 'q' pour quitter
```

### Service systemd (démarrage auto)
```bash
sudo nano /etc/systemd/system/smartiglab-vision.service
```

Contenu:
```ini
[Unit]
Description=SmartIGLab Vision Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/IoT/vision
Environment="PATH=/home/pi/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 /home/pi/IoT/vision/people_counter.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activation:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smartiglab-vision.service
sudo systemctl start smartiglab-vision.service
sudo systemctl status smartiglab-vision.service
```

Logs:
```bash
sudo journalctl -u smartiglab-vision.service -f
```

## Publication MQTT
- **Topic**: `smartiglab/vision/people_count`
- **QoS**: 1
- **Retain**: False
- **Payload JSON**:
```json
{
  "n": 12,
  "fps": 6.3,
  "ts": 1733155200,
  "capacity": 40
}
```

## Performances attendues

### Raspberry Pi 4 (4 GB)
- YOLOv8n @ 640x480: **5-8 FPS**
- YOLOv8n @ 320x240: **10-15 FPS**

### Optimisations possibles
1. Réduire résolution: `CAM_WIDTH=320`, `CAM_HEIGHT=240`
2. Réduire imgsz YOLO: `YOLO_IMGSZ=320`
3. Augmenter seuil: `YOLO_CONF=0.6`
4. Export ONNX/TensorRT (avancé)

## Calibration

### Placement caméra
- Hauteur: 2.5-3m pour vue d'ensemble
- Angle: légèrement vers le bas (20-30°)
- Éviter contre-jour et reflets
- Couvrir zone d'entrée/passage principal

### Ajustement seuil confiance
- `YOLO_CONF=0.4`: plus de détections, possibles faux positifs
- `YOLO_CONF=0.6`: moins de faux positifs, risque manquer personnes éloignées

### Zone d'intérêt (ROI) - à implémenter
Pour exclure couloirs/portes, modifier `detect_people()` avec découpe de frame.

## Troubleshooting

### Caméra non détectée
```bash
# Vérifier périphériques
v4l2-ctl --list-devices

# Tester avec différents index
# Modifier CAM_INDEX dans .env
```

### FPS trop faible
- Réduire résolution caméra
- Réduire YOLO_IMGSZ
- Vérifier charge CPU: `htop`
- Désactiver services non essentiels

### Erreur MQTT
- Vérifier broker actif: `mosquitto_sub -h <MQTT_HOST> -t '#' -v`
- Tester connexion: `telnet <MQTT_HOST> 1883`
- Vérifier credentials si auth activée

### Performance GPU (optionnel)
Pour Pi 5 ou avec accélérateur:
```bash
pip3 install onnxruntime-gpu
# Exporter modèle: yolo export model=yolov8n.pt format=onnx
```