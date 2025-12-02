# ESP32 Display - SmartIGLab

Firmware pour écran ESP32-S3 intégré affichant le statut de l'auditoire IGLab.

## Matériel

**Écran utilisé**: ESP32-S3 avec TFT display intégré  
Lien: https://nl.aliexpress.com/item/1005008789890066.html

Spécifications typiques:
- MCU: ESP32-S3
- Display: TFT 1.9" (170×320 pixels)
- Driver: ST7789 ou ILI9341
- Wi-Fi intégré
- Batterie rechargeable (optionnel selon modèle)

## Architecture

```
┌─────────────────────┐
│   Raspberry Pi      │
│   Backend (FastAPI) │
│   Port 8000         │
└──────────┬──────────┘
           │ HTTP GET /status
           │ (toutes les 2s)
           ▼
┌─────────────────────┐
│   ESP32-S3          │
│   ┌───────────────┐ │
│   │   Display TFT │ │
│   │   170×320     │ │
│   │               │ │
│   │  OCCUPÉ/LIBRE │ │
│   │  Personnes: X │ │
│   │  Places: Y    │ │
│   │  T°: 22.5°C   │ │
│   └───────────────┘ │
└─────────────────────┘
```

## Installation

### Prérequis
- PlatformIO (VS Code extension recommandée)
- Câble USB-C pour flasher l'ESP32

### Setup

1. **Ouvrir le projet dans PlatformIO**
```powershell
cd "C:\Users\Ouiam\OneDrive - UMONS\USB KEY - STUDIES\MA2\Projet\IoT\firmware\esp32-display"
code .
```

2. **Configurer les identifiants Wi-Fi**

Éditer `src/main.cpp`, lignes 9-11:
```cpp
const char* WIFI_SSID = "Raspberry_Pi_AP";     // SSID du Pi
const char* WIFI_PASS = "votre_mot_de_passe";  // Mot de passe
const char* API_URL = "http://192.168.1.10:8000/status";  // IP du Pi
```

3. **Ajuster la configuration écran si nécessaire**

Si l'affichage est incorrect, modifier `platformio.ini`:
```ini
; Pour rotation portrait (défaut)
-DTFT_WIDTH=170
-DTFT_HEIGHT=320

; Pour rotation paysage
-DTFT_WIDTH=320
-DTFT_HEIGHT=170
```

Les pins GPIO sont préconfigurés pour le modèle standard ESP32-S3 display.

4. **Compiler et flasher**
```
PlatformIO: Build
PlatformIO: Upload
PlatformIO: Monitor (pour voir les logs)
```

Ou via ligne de commande:
```powershell
pio run --target upload
pio device monitor
```

## Fonctionnement

### Au démarrage
1. Initialise l'écran TFT
2. Se connecte au Wi-Fi du Raspberry Pi
3. Affiche "Wi-Fi OK!" si connexion réussie

### En boucle
1. Toutes les **2 secondes**: `GET http://raspberry-ip:8000/status`
2. Parse le JSON reçu
3. Met à jour l'affichage avec:
   - Statut: **OCCUPÉ** (rouge) ou **LIBRE** (vert)
   - Nombre de personnes détectées
   - Places libres restantes
   - Température et humidité (DHT22)
   - État fenêtre (ouverte/fermée)
   - État Hyperplanning
   - FPS vision (en bas)

### Gestion erreurs
- Si Wi-Fi perdu → "Wi-Fi deconnecte" + reconnexion auto
- Si API inaccessible → "Donnees invalides"
- Timeout HTTP: 5 secondes

## Affichage type

```
┌─────────────────┐
│  SmartIGLab     │
│                 │
│    OCCUPÉ       │  ← Rouge si occupé, vert si libre
│                 │
│  Personnes: 12  │
│  Places libres: 28 │
│                 │
│  Temperature: 22.5 C │
│  Humidite: 45.0 %   │
│  Fenetre: Fermee    │
│                 │
│  Planning: Cours    │
│                 │
│  FPS: 6.3    2s │  ← FPS vision, dernière MAJ
└─────────────────┘
```

## Personnalisation

### Couleurs (dans `main.cpp`)
```cpp
#define COLOR_LIBRE    0x07E0   // Vert
#define COLOR_OCCUPE   0xF800   // Rouge
#define COLOR_TEXT     0xFFFF   // Blanc
#define COLOR_GRAY     0x7BEF   // Gris
```

Format: RGB565 (16-bit)

### Intervalle de rafraîchissement
```cpp
const unsigned long REFRESH_INTERVAL = 2000;  // 2 secondes
```

Plus court = plus réactif, plus de trafic réseau.

### Layout
Modifier les positions Y dans `displayStatus()`:
```cpp
int yPos = 60;  // Position verticale initiale
yPos += 30;     // Espacement entre lignes
```

## Consommation

- **Wi-Fi actif + écran**: ~150-200 mA
- **Autonomie** (batterie 1000 mAh): ~5-7 heures
- **Recommandation**: alimentation USB permanente (5V/1A)

## Troubleshooting

### Écran blanc/noir
- Vérifier les pins dans `platformio.ini`
- Essayer rotation différente: `tft.setRotation(0-3)`
- Tester driver ILI9341 si ST7789 ne marche pas

### Pas de connexion Wi-Fi
```cpp
// Activer debug série
Serial.begin(115200);
// Voir logs dans PlatformIO Monitor
```
- Vérifier SSID/password
- Confirmer que le Pi est en mode AP
- Tester ping depuis PC vers IP du Pi

### API inaccessible
```
curl http://192.168.1.10:8000/status
```
- Vérifier backend démarré sur Pi
- Firewall Pi bloque port 8000 ?
- Bonne IP dans `API_URL` ?

### Affichage flicker
- Ajouter délai dans loop: `delay(100)`
- Utiliser sprites/buffering (avancé)

## Optimisations futures

1. **Deep sleep**: entre refreshs pour économie batterie
2. **WebSocket**: au lieu de polling HTTP
3. **OTA updates**: flasher via Wi-Fi
4. **Touch screen**: si modèle avec tactile
5. **Graphiques**: historique température, occupation

## Schéma connexion

```
┌──────────────────────────────────┐
│        Raspberry Pi (AP)         │
│  SSID: Raspberry_Pi_AP           │
│  IP: 192.168.1.10                │
│  Backend: :8000/status           │
└───────────────┬──────────────────┘
                │ Wi-Fi
                │
        ┌───────▼───────┐
        │   ESP32-S3    │
        │   Display     │
        │   (Client)    │
        └───────────────┘
```

Pas de câblage physique nécessaire, tout en Wi-Fi !

## Alternative: Affichage Web

Si l'écran ESP32 n'arrive pas tout de suite, utilisez une **tablette** en mode kiosk affichant la page web (étape suivante du projet).
