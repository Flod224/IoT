"""
SmartIGLab - Lecteur de capteurs GPIO
======================================
Compatible Raspberry Pi uniquement (numérotation BCM)

Capteurs supportés:
  - DHT22: Température et humidité
  - Reed switch: Détection ouverture fenêtre

Thread-safe avec lecture automatique en arrière-plan.
"""

import time
import logging
from typing import Optional
from threading import Thread, Lock

logger = logging.getLogger(__name__)

# Import des bibliothèques GPIO (optionnelles en développement)
try:
    import RPi.GPIO as GPIO
    import adafruit_dht
    import board
    GPIO_AVAILABLE = True
    logger.info("✓ Bibliothèques GPIO chargées")
except ImportError as e:
    GPIO_AVAILABLE = False
    logger.warning("⚠️  GPIO non disponibles - Capteurs désactivés")
    logger.warning(f"Raison: {e}")
    logger.warning("Installation sur Raspberry Pi:")
    logger.warning("  1. sudo apt-get update")
    logger.warning("  2. sudo apt-get install python3-rpi.gpio python3-dev")
    logger.warning("  3. pip install adafruit-circuitpython-dht")
    logger.warning("Le backend continuera sans capteurs")


class SensorReader:
    """
    Lecteur de capteurs environnementaux GPIO
    
    Thread-safe avec boucle de lecture automatique en arrière-plan.
    Gère les erreurs temporaires du DHT22 (courantes avec ce capteur).
    """
    
    def __init__(self, dht_pin: int, reed_pin: int, interval: float = 10.0):
        """
        Initialise le lecteur de capteurs
        
        Args:
            dht_pin: Numéro GPIO BCM pour DHT22 (défaut: 4)
            reed_pin: Numéro GPIO BCM pour reed switch (défaut: 17)
            interval: Intervalle de lecture en secondes (défaut: 10s)
        """
        self.dht_pin = dht_pin
        self.reed_pin = reed_pin
        self.interval = interval
        
        # État partagé (thread-safe)
        self._lock = Lock()
        self._temperature: Optional[float] = None
        self._humidity: Optional[float] = None
        self._window_open: Optional[bool] = False  # Défaut: fermée
        self._last_update: Optional[float] = None
        self._running = False
        self._error_count = 0
        
        # Devices
        self._dht_device = None
        self._thread: Optional[Thread] = None
    
    @property
    def temperature(self) -> Optional[float]:
        """Température en °C (thread-safe)"""
        with self._lock:
            return self._temperature
    
    @property
    def humidity(self) -> Optional[float]:
        """Humidité relative en % (thread-safe)"""
        with self._lock:
            return self._humidity
    
    @property
    def window_open(self) -> Optional[bool]:
        """État fenêtre (thread-safe)"""
        with self._lock:
            return self._window_open
    
    @property
    def last_update(self) -> Optional[float]:
        """Timestamp dernière lecture (thread-safe)"""
        with self._lock:
            return self._last_update
    
    def get_data(self) -> dict:
        """
        Retourne toutes les données des capteurs
        
        Thread-safe avec lock pour garantir la cohérence.
        
        Returns:
            dict avec temperature, humidity, window_open, last_update, error_count
        """
        with self._lock:
            return {
                "temperature": self._temperature,
                "humidity": self._humidity,
                "window_open": self._window_open,
                "last_update": self._last_update,
                "error_count": self._error_count
            }
    
    def _setup_gpio(self):
        """
        Configure les pins GPIO du Raspberry Pi
        
        - DHT22: Utilise board.Dxx pour la compatibilité Adafruit
        - Reed switch: Configuré en INPUT avec pull-up (HIGH = ouvert)
        
        Raises:
            Exception si les pins sont mal configurés ou déjà utilisés
        """
        if not GPIO_AVAILABLE:
            logger.warning("⚠️  GPIO non disponibles - capteurs désactivés")
            return
        
        try:
            # DHT22
            dht_board_pin = getattr(board, f"D{self.dht_pin}")
            self._dht_device = adafruit_dht.DHT22(dht_board_pin, use_pulseio=False)
            logger.info(f"✓ DHT22 configuré sur GPIO {self.dht_pin}")
            
            # Reed switch
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.reed_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"✓ Reed switch configuré sur GPIO {self.reed_pin}")
            
        except Exception as e:
            logger.error(f"✗ Erreur configuration GPIO: {e}")
            logger.error(f"Vérifiez: 1) Connexions physiques, 2) Permissions (sudo usermod -a -G gpio $USER), 3) Numéros de pin")
            raise
    
    def _read_sensors(self):
        """
        Effectue une lecture unique des capteurs
        
        Le DHT22 peut échouer occasionnellement (timing capricieux).
        Les erreurs temporaires sont normales et gérées automatiquement.
        
        Returns:
            tuple (temperature, humidity, window_state) ou (None, None, None) si erreur
        """
        if not GPIO_AVAILABLE:
            # GPIO non disponibles - retourner None
            return None, None, None
        
        try:
            # DHT22
            temp = self._dht_device.temperature
            hum = self._dht_device.humidity
            
            # Reed switch - DÉSACTIVÉ (toujours fermée)
            # Décommenter si capteur branché:
            # window = GPIO.input(self.reed_pin) == GPIO.HIGH
            window = False  # Forcé à False si capteur non branché
            
            return temp, hum, window
            
        except RuntimeError as e:
            # DHT22 peut échouer occasionnellement (timing)
            logger.debug(f"Erreur temporaire DHT22: {e}")
            return None, None, None
        except Exception as e:
            logger.error(f"✗ Erreur lecture capteurs: {e}")
            logger.error(f"Vérifiez la connexion du DHT22 (pin GPIO {self.dht_pin}) et du reed switch (pin GPIO {self.reed_pin})")
            return None, None, None
    
    def _update_state(self, temp: Optional[float], hum: Optional[float], window: Optional[bool]):
        """
        Met à jour l'état interne de manière thread-safe
        
        Arrondit les valeurs à 1 décimale. Compte les erreurs consécutives
        pour alerter en cas de problème matériel persistant.
        Enregistre dans la base de données.
        
        Args:
            temp: Température en °C (None si erreur)
            hum: Humidité en % (None si erreur)
            window: État fenêtre True=ouverte (None si erreur)
        """
        with self._lock:
            if temp is not None and hum is not None:
                self._temperature = round(temp, 1)
                self._humidity = round(hum, 1)
                self._window_open = window
                self._last_update = time.time()
                self._error_count = 0
                
                # Enregistrer dans la base de données
                try:
                    from app.database import add_sensor_reading
                    add_sensor_reading(
                        timestamp=self._last_update,
                        temperature=self._temperature,
                        humidity=self._humidity,
                        window_open=self._window_open
                    )
                except Exception as e:
                    logger.debug(f"Erreur enregistrement DB: {e}")
                    
            elif GPIO_AVAILABLE:  # Only count errors if GPIO should be working
                self._error_count += 1
                if self._error_count % 10 == 0:
                    logger.warning(f"⚠️ {self._error_count} échecs de lecture consécutifs - vérifiez les capteurs")
    
    def _run_loop(self):
        """
        Boucle principale du thread de lecture
        
        Lit les capteurs en continu à intervalle régulier.
        Tourne en tâche de fond (daemon thread).
        """
        logger.info(f"Démarrage lecture capteurs (intervalle: {self.interval}s)")
        
        while self._running:
            temp, hum, window = self._read_sensors()
            self._update_state(temp, hum, window)
            
            if temp is not None:
                logger.info(f"Capteurs: T={temp}°C, RH={hum}%, Fenêtre={'ouverte' if window else 'fermée'}")
            
            time.sleep(self.interval)
        
        logger.info("Boucle capteurs arrêtée")
    
    def start(self):
        """
        Démarre le thread de lecture des capteurs
        
        Configure les GPIO puis lance la boucle de lecture.
        Appeler une seule fois au démarrage de l'application.
        """
        if self._running:
            logger.warning("Lecture capteurs déjà en cours")
            return
        
        self._setup_gpio()
        
        self._running = True
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Lecture capteurs démarrée")
    
    def stop(self):
        """
        Arrête proprement le thread et nettoie les GPIO
        
        Appelé lors de l'arrêt de l'application.
        """
        if not self._running:
            return
        
        logger.info("Arrêt lecture capteurs...")
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        self.cleanup()
    
    def cleanup(self):
        """
        Libère les ressources GPIO
        
        Appelé automatiquement par stop().
        Important pour éviter les warnings "channel already in use".
        """
        if not GPIO_AVAILABLE:
            return
        
        if self._dht_device:
            try:
                self._dht_device.exit()
                logger.info("✓ DHT22 arrêté")
            except Exception as e:
                logger.debug(f"Erreur arrêt DHT22: {e}")
        
        try:
            GPIO.cleanup()
            logger.info("✓ GPIO nettoyés")
        except Exception as e:
            logger.debug(f"Erreur nettoyage GPIO: {e}")
