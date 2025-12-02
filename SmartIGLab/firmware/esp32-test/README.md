# Test ESP32 (sans écran) - SmartIGLab

Version de test pour ESP32 **sans écran TFT** utilisant uniquement le **moniteur série** pour vérifier:
- ✅ Connexion Wi-Fi
- ✅ Requête HTTP vers l'API
- ✅ Parsing JSON
- ✅ Affichage des données

## Matériel nécessaire

- 1x ESP32 (n'importe quel modèle: ESP32-WROOM, ESP32-S3, etc.)
- 1x Câble USB
- LED intégrée (présente sur tous les ESP32)

**Pas besoin d'écran** pour ce test !

## Installation

### 1. Ouvrir le projet
```powershell
cd "C:\Users\Ouiam\OneDrive - UMONS\USB KEY - STUDIES\MA2\Projet\IoT\firmware\esp32-test"
code .
```

### 2. Configurer Wi-Fi et API

Éditer `src/main.cpp`, lignes 7-9:
```cpp
const char* WIFI_SSID = "VotreWiFi";          // Nom de votre réseau
const char* WIFI_PASS = "VotreMotDePasse";    // Mot de passe
const char* API_URL = "http://192.168.1.10:8000/status";  // IP du Pi
```

**Important**: Pour tester localement sans Pi, vous pouvez utiliser l'IP de votre PC si vous lancez le backend dessus.

### 3. Brancher ESP32

Connecter l'ESP32 en USB à votre PC.

### 4. Compiler et flasher

Dans VS Code avec PlatformIO:
```
1. Build (icône ✓ en bas)
2. Upload (icône → en bas)
3. Monitor (icône 🔌 en bas)
```

Ou en ligne de commande:
```powershell
pio run --target upload
pio device monitor
```

## Lecture du moniteur série

### Démarrage
```
========================================
   SmartIGLab - TEST ESP32 (sans écran)
========================================

┌─────────────────────────────────────┐
│     CONNEXION WI-FI                 │
└─────────────────────────────────────┘
SSID: VotreWiFi
Connexion en cours.....

✓ Wi-Fi connecté avec succès!
  IP locale: 192.168.1.50
  Signal (RSSI): -45 dBm
  Passerelle: 192.168.1.1

--- Démarrage des tests ---
```

### Test API (toutes les 5 secondes)
```
┌─────────────────────────────────────┐
│     TEST RÉCUPÉRATION /status       │
└─────────────────────────────────────┘
URL: http://192.168.1.10:8000/status
Timestamp: 42

Envoi requête HTTP GET...
Code HTTP: 200 (temps: 156 ms)
✓ Réponse reçue!

--- Réponse brute (JSON) ---
{"occupied":true,"free_seats":28,"people_count":12, ...}
--- Fin réponse ---

✓ JSON parsé avec succès!

╔═══════════════════════════════════════╗
║     DONNÉES RÉCUPÉRÉES                ║
╚═══════════════════════════════════════╝
Statut: 🔴 OCCUPÉ

--- Comptage ---
Personnes détectées: 12
Places libres: 28
Capacité totale: 40

--- Environnement ---
Température: 22.5 °C
Humidité: 45.3 %
Fenêtre: Fermée

--- Hyperplanning ---
État: course_en_cours
Cours: Cours IoT - MA2

--- Vision YOLO ---
FPS: 6.3

═══════════════════════════════════════
```

## Feedback visuel

La **LED intégrée** de l'ESP32 indique l'état:
- **Clignote lentement** (500ms) = Wi-Fi connecté, tout fonctionne
- **Éteinte** = problème Wi-Fi
- **Flash unique** = connexion Wi-Fi réussie au boot

## Scénarios de test

### ✅ Test 1: Connexion Wi-Fi seule
1. Démarrer l'ESP32
2. Vérifier dans le moniteur série:
   - "✓ Wi-Fi connecté avec succès!"
   - IP attribuée affichée
3. LED clignote = OK

### ✅ Test 2: Backend sur votre PC (sans Pi)
Si vous n'avez pas encore le Pi:
```powershell
# Terminal 1: Lancer backend sur PC
cd backend
$env:VISION_ENABLED="False"
uvicorn app.main:app --host 0.0.0.0 --reload

# Noter l'IP de votre PC (ex: 192.168.1.100)
ipconfig
```

```cpp
// Dans main.cpp
const char* API_URL = "http://192.168.1.100:8000/status";  // IP de votre PC
```

### ✅ Test 3: Backend sur Raspberry Pi
```cpp
// Dans main.cpp
const char* API_URL = "http://192.168.1.10:8000/status";  // IP du Pi
```

Sur le Pi:
```bash
cd ~/IoT/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### ✅ Test 4: Données simulées vs réelles
Comparer les valeurs affichées:
- Si `temperature = 0` ou `people_count = 0` → données simulées (backend en mode test)
- Si valeurs réalistes → capteurs et caméra fonctionnent !

## Troubleshooting

### Erreur: Échec connexion Wi-Fi
```
✗ ÉCHEC connexion Wi-Fi!
```
**Solutions:**
- Vérifier SSID/password dans le code
- S'assurer que le réseau est visible (2.4 GHz, pas 5 GHz)
- Rapprocher ESP32 du routeur
- Désactiver isolation AP si en mode hotspot

### Erreur: Code HTTP -1
```
✗ Échec connexion HTTP
```
**Solutions:**
```powershell
# Tester depuis PC si backend accessible
curl http://192.168.1.10:8000/status

# Vérifier IP correcte
ping 192.168.1.10

# Vérifier backend démarré
# Sur Pi ou PC: uvicorn app.main:app --host 0.0.0.0
```

### Erreur: Code HTTP 404
```
Code HTTP: 404
```
**Solution:** Vérifier l'URL complète avec `/status` à la fin

### Moniteur série vide
- Baud rate incorrect → vérifier `monitor_speed = 115200`
- Appuyer sur bouton **BOOT** ou **RESET** de l'ESP32
- Vérifier port COM correct dans PlatformIO

### JSON parse error
```
✗ Erreur parsing JSON: ...
```
**Solution:** Backend retourne mauvais format
```bash
# Tester manuellement
curl http://192.168.1.10:8000/status | jq
```

## Passage à l'écran

Une fois ce test validé (Wi-Fi + API OK), vous pourrez simplement:
1. Brancher l'écran ESP32-S3 display
2. Utiliser le code dans `firmware/esp32-display/`
3. Même config Wi-Fi/API, mais avec affichage graphique

Le code série actuel vous permet de **valider toute la chaîne** avant d'avoir l'écran physique !

## Commandes utiles

```powershell
# Moniteur série seul (après upload)
pio device monitor

# Upload + monitor direct
pio run -t upload && pio device monitor

# Changer vitesse baud si besoin
pio device monitor -b 115200

# Lister ports COM disponibles
pio device list
```

## Exemple complet de sortie réussie

Vous devriez voir un cycle comme ça toutes les 5 secondes:
1. "TEST RÉCUPÉRATION /status"
2. "Code HTTP: 200"
3. JSON affiché
4. Toutes les données parsées et formatées
5. LED clignote

= **Tout fonctionne !** 🎉

Une fois validé, passez à l'écran TFT avec le même code adapté.
