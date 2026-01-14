"""
SmartIGLab - Base de données SQLite
====================================
Stockage local de l'historique des capteurs.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import threading

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "smartiglab.db"

# Lock pour les accès concurrents
db_lock = threading.Lock()


def init_database():
    """Initialise la base de données et crée les tables"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Table historique capteurs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                temperature REAL,
                humidity REAL,
                window_open INTEGER
            )
        """)
        
        # Index pour recherches rapides par timestamp
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON sensor_history(timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"✓ Base de données initialisée: {DB_PATH}")


def add_sensor_reading(timestamp: float, temperature: float = None, 
                       humidity: float = None, window_open: bool = None):
    """Ajoute une lecture de capteur dans l'historique"""
    with db_lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sensor_history (timestamp, temperature, humidity, window_open)
                VALUES (?, ?, ?, ?)
            """, (timestamp, temperature, humidity, 1 if window_open else 0))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erreur enregistrement capteur: {e}")


def get_sensor_history(hours: int = 24, limit: int = 1000) -> List[Dict]:
    """
    Récupère l'historique des capteurs
    
    Args:
        hours: Nombre d'heures à récupérer (défaut: 24h)
        limit: Nombre max d'entrées (défaut: 1000)
    
    Returns:
        Liste de dict {timestamp, temperature, humidity, window_open}
    """
    with db_lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Timestamp limite (maintenant - X heures)
            from time import time
            min_timestamp = time() - (hours * 3600)
            
            cursor.execute("""
                SELECT timestamp, temperature, humidity, window_open
                FROM sensor_history
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (min_timestamp, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convertir en liste de dicts
            history = []
            for row in rows:
                history.append({
                    "timestamp": row[0],
                    "temperature": row[1],
                    "humidity": row[2],
                    "window_open": bool(row[3])
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Erreur récupération historique: {e}")
            return []


def cleanup_old_data(days: int = 30):
    """Supprime les données plus anciennes que X jours"""
    with db_lock:
        try:
            from time import time
            min_timestamp = time() - (days * 86400)
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM sensor_history
                WHERE timestamp < ?
            """, (min_timestamp,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted > 0:
                logger.info(f"Nettoyage: {deleted} entrée(s) supprimée(s)")
                
        except Exception as e:
            logger.error(f"Erreur nettoyage: {e}")
