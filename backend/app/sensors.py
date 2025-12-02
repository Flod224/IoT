"""
Module de lecture des capteurs GPIO (DHT22 + reed switch)
Compatible Raspberry Pi uniquement
"""

import time
import logging
from typing import Optional
from threading import Thread, Lock

logger = logging.getLogger(__name__)

# Import des bibliothèques GPIO (requis)
try:
    import RPi.GPIO as GPIO
    import adafruit_dht
    import board
    GPIO_AVAILABLE = True
    logger.info("Bibliothèques GPIO chargées avec succès")
except ImportError as e:
    GPIO_AVAILABLE = False
    logger.error(f"ERREUR: Bibliothèques GPIO non disponibles: {e}")
    logger.error("Installation requise: sudo apt-get install python3-rpi.gpio && pip install adafruit-circuitpython-dht")
    raise ImportError("Bibliothèques GPIO requises non trouvées") from e


class SensorReader:
    """Lecteur de capteurs GPIO (DHT22 + reed switch)"""
    
    def __init__(self, dht_pin: int, reed_pin: int, interval: float = 10.0):
        self.dht_pin = dht_pin
        self.reed_pin = reed_pin
        self.interval = interval
        
        # État partagé (thread-safe)
        self._lock = Lock()
        self._temperature: Optional[float] = None
        self._humidity: Optional[float] = None
        self._window_open: Optional[bool] = None
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
        """Retourne toutes les données (thread-safe)"""
        with self._lock:
            return {
                "temperature": self._temperature,
                "humidity": self._humidity,
                "window_open": self._window_open,
                "last_update": self._last_update,
                "error_count": self._error_count
            }
    
    def _setup_gpio(self):
        """Configure les GPIO"""
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
        """Lit les capteurs une fois"""
        try:
            # DHT22
            temp = self._dht_device.temperature
            hum = self._dht_device.humidity
            
            # Reed switch (HIGH = ouvert avec pull-up)
            window = GPIO.input(self.reed_pin) == GPIO.HIGH
            
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
        """Met à jour l'état (thread-safe)"""
        with self._lock:
            if temp is not None and hum is not None:
                self._temperature = round(temp, 1)
                self._humidity = round(hum, 1)
                self._window_open = window
                self._last_update = time.time()
                self._error_count = 0
            else:
                self._error_count += 1
                if self._error_count % 10 == 0:
                    logger.warning(f"⚠️ {self._error_count} échecs de lecture consécutifs - vérifiez les capteurs")
    
    def _run_loop(self):
        """Boucle de lecture (thread)"""
        logger.info(f"Démarrage lecture capteurs (intervalle: {self.interval}s)")
        
        while self._running:
            temp, hum, window = self._read_sensors()
            self._update_state(temp, hum, window)
            
            if temp is not None:
                logger.info(f"Capteurs: T={temp}°C, RH={hum}%, Fenêtre={'ouverte' if window else 'fermée'}")
            
            time.sleep(self.interval)
        
        logger.info("Boucle capteurs arrêtée")
    
    def start(self):
        """Démarre la lecture en arrière-plan"""
        if self._running:
            logger.warning("Lecture capteurs déjà en cours")
            return
        
        self._setup_gpio()
        
        self._running = True
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Lecture capteurs démarrée")
    
    def stop(self):
        """Arrête la lecture"""
        if not self._running:
            return
        
        logger.info("Arrêt lecture capteurs...")
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        self.cleanup()
    
    def cleanup(self):
        """Nettoyage GPIO"""
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
