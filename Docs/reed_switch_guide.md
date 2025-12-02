# Reed Switch - Capteur d'ouverture de fenêtre

## Qu'est-ce qu'un reed switch ?

Un **reed switch** (interrupteur à lames souples) est un capteur magnétique simple composé de deux parties:

```
┌─────────────────┐         ┌──────┐
│  Reed Switch    │         │Aimant│
│  (sur cadre)    │  ◄───►  │ (sur │
│  ══════         │  distance│fenêtre)
└─────────────────┘         └──────┘
```

### Fonctionnement

**Fenêtre fermée:**
```
┌───────┬─────────┐
│ Cadre │ Fenêtre │
│  [R]  │   [A]   │  ← Aimant proche du reed
│       │         │
└───────┴─────────┘

Aimant PROCHE → Lames magnétiques SE TOUCHENT → Circuit FERMÉ
```

**Fenêtre ouverte:**
```
┌───────┐      ┌─────────┐
│ Cadre │      │ Fenêtre │
│  [R]  │ ←→   │   [A]   │  ← Aimant éloigné
│       │      │         │
└───────┘      └─────────┘

Aimant LOIN → Lames SÉPARÉES → Circuit OUVERT
```

## Câblage sur Raspberry Pi

### Matériel nécessaire
- 1x Reed switch (ex: MC-38 ou similaire)
- 1x Aimant (souvent fourni avec le reed)
- 2x Câbles dupont femelle-femelle

### Schéma de connexion

```
Raspberry Pi GPIO                Reed Switch
┌────────────┐                  ┌──────────┐
│            │                  │          │
│  GPIO 17 ──┼──────────────────┤ Borne 1  │
│   (pin 11) │                  │          │
│            │                  │          │
│  GND ──────┼──────────────────┤ Borne 2  │
│   (pin 9)  │                  │          │
│            │                  └──────────┘
└────────────┘
```

### Configuration dans le code

```python
import RPi.GPIO as GPIO

REED_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(REED_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Lecture
window_open = GPIO.input(REED_PIN) == GPIO.HIGH

# HIGH (1) = circuit ouvert = fenêtre OUVERTE
# LOW (0)  = circuit fermé  = fenêtre FERMÉE
```

**Avec pull-up activé:**
- Fenêtre fermée → aimant proche → reed fermé → GPIO lit LOW (0)
- Fenêtre ouverte → aimant loin → reed ouvert → GPIO lit HIGH (1) via pull-up

## Installation physique

### Étape 1: Positionnement
```
        Cadre fixe          Fenêtre mobile
        ┌────────┐          ┌────────┐
        │        │          │        │
Haut    │  [R]   │◄─ 1cm ─►│  [A]   │
        │        │          │        │
        └────────┘          └────────┘
```

- Reed switch sur la partie **fixe** (cadre)
- Aimant sur la partie **mobile** (fenêtre)
- Distance quand fermé: **< 1 cm** pour détection fiable

### Étape 2: Fixation
- Colle double-face ou vis (selon boîtier)
- Aligner reed et aimant parfaitement
- Tester plusieurs fois l'ouverture/fermeture

### Étape 3: Câblage
- Faire passer les fils discrètement
- Protéger avec gaine si exposition extérieure
- Connecter au Raspberry Pi GPIO 17 + GND

## Test rapide

### Sur Raspberry Pi (avec reed branché):

```bash
# Installer gpiozero (plus simple)
pip3 install gpiozero

# Test en Python
python3 << EOF
from gpiozero import Button
from time import sleep

reed = Button(17)

print("Test reed switch (Ctrl+C pour arrêter)")
while True:
    if reed.is_pressed:
        print("Fenêtre FERMÉE (aimant proche)")
    else:
        print("Fenêtre OUVERTE (aimant loin)")
    sleep(0.5)
EOF
```

### Test avec le backend:

```bash
cd ~/IoT/backend
source venv/bin/activate

# Éditer .env: SENSOR_READ_INTERVAL=2
uvicorn app.main:app --reload

# Dans un autre terminal:
curl http://localhost:8000/status | jq '.environment.window_open'

# Ouvrir/fermer la fenêtre et relancer curl
```

## Dépannage

### Reed ne détecte rien
- Vérifier distance reed/aimant (< 1 cm quand fermé)
- Inverser polarité de l'aimant si besoin
- Tester continuité avec multimètre

### Fausses détections
- Aimant trop proche en permanence → éloigner légèrement
- Interférences magnétiques → éloigner sources métalliques

### GPIO ne lit rien
```bash
# Tester GPIO directement
gpio readall  # Voir état pin 17

# Permissions
sudo usermod -aG gpio $USER
```

## Alternatives

Si pas de reed switch disponible:

1. **Capteur infrarouge** (émetteur/récepteur)
2. **Capteur ultrason** (mesure distance)
3. **Microswitch mécanique** (bouton-poussoir)
4. **Capteur Hall effect** (plus sensible au magnétisme)

Pour ce projet, le **reed switch est le plus simple et fiable** pour détecter ouverture/fermeture binaire.

## Intégration dans SmartIGLab

Le reed switch permet de:
- Détecter si fenêtres ouvertes → afficher sur dashboard
- Corréler avec température (fenêtre ouverte = refroidissement)
- Alerter si température basse + fenêtre ouverte longtemps (économie énergie)

Données transmises au backend via GPIO → API `/status` → Dashboard/ESP32.
