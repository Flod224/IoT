"""
Script de test du backend (hors Raspberry Pi)

NOTE IMPORTANTE:
- Ce script teste la STRUCTURE du code, pas les vrais capteurs
- Sur PC Windows: données SIMULÉES (pas de GPIO, pas de caméra)
- Sur Raspberry Pi avec vrais capteurs: lancer le serveur complet (uvicorn)

Capteurs testés:
- DHT22: capteur température/humidité (valeurs simulées ici)
- Reed switch: capteur magnétique fenêtre ouvert/fermé (valeurs simulées ici)
- Vision YOLO: comptage personnes via webcam (désactivé dans ces tests)
"""

import sys
import time
from pathlib import Path

# Ajouter le backend au path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

def test_models():
    """Test des modèles Pydantic"""
    print("=== Test Models ===")
    from app.models import SystemStatus, EnvironmentData, HyperplanningData
    
    env = EnvironmentData(temperature=22.5, humidity=45.0, window_open=False)
    hp = HyperplanningData(state="libre")
    
    status = SystemStatus(
        occupied=False,
        free_seats=40,
        people_count=0,
        capacity=40,
        environment=env,
        hyperplanning=hp,
        vision_fps=0.0,
        updated_at=time.time()
    )
    
    print(status.model_dump_json(indent=2))
    print("✓ Models OK\n")


def test_sensor_simulation():
    """Test du module capteurs en mode simulation (pas de vrais GPIO)"""
    print("=== Test Sensors (SIMULATION - pas de vrais capteurs) ===")
    print("Sur PC Windows: génère des données aléatoires")
    print("Sur Raspberry Pi: lirait les vrais GPIO DHT22 + reed switch\n")
    
    from app.sensors import SensorReader
    
    reader = SensorReader(dht_pin=4, reed_pin=17, interval=2.0)
    reader.start()
    
    print("Attente de 5 secondes pour collecter des données simulées...")
    time.sleep(5)
    
    data = reader.get_data()
    print(f"\nDonnées (SIMULÉES):")
    print(f"  Température: {data['temperature']}°C (DHT22 simulated)")
    print(f"  Humidité: {data['humidity']}% (DHT22 simulated)")
    print(f"  Fenêtre: {'ouverte' if data['window_open'] else 'fermée'} (Reed switch simulated)")
    print(f"  Dernière lecture: {data['last_update']}")
    
    reader.stop()
    print("\n✓ Structure du module capteurs OK")
    print("  → Sur Pi avec vrais capteurs: remplacer simulation par GPIO.input()\n")


def test_hyperplanning():
    """Test du client Hyperplanning (mock)"""
    print("=== Test Hyperplanning (mock) ===")
    from app.hyperplanning import HyperplanningClient
    
    client = HyperplanningClient(url="", room_id="iglab", refresh_interval=3.0)
    client.start()
    
    time.sleep(4)
    
    status = client.get_status()
    print(f"État: {status['state']}")
    print(f"Cours: {status['title']}")
    
    client.stop()
    print("✓ Hyperplanning OK\n")


def test_integration():
    """Test d'intégration (sans caméra, capteurs simulés)"""
    print("=== Test Intégration (SANS CAMÉRA RÉELLE) ===")
    print("Vision: désactivée (pas de flux vidéo)")
    print("Capteurs: simulés (pas de vrais GPIO)\n")
    
    import os
    os.environ["VISION_ENABLED"] = "False"
    
    from app.config import settings
    from app.sensors import SensorReader
    from app.hyperplanning import HyperplanningClient
    
    # Démarrer services
    print("Démarrage des services en arrière-plan...")
    sensors = SensorReader(settings.dht22_pin, settings.reed_switch_pin, 2.0)
    sensors.start()
    
    hp = HyperplanningClient("", "iglab", 5.0)
    hp.start()
    
    # Simuler agrégation
    print("Collecte de données pendant 3 secondes...")
    time.sleep(3)
    
    sensor_data = sensors.get_data()
    hp_data = hp.get_status()
    
    print("\n📊 Données agrégées (comme dans GET /status):")
    print(f"  🌡️  Température: {sensor_data['temperature']}°C (simulé)")
    print(f"  💧 Humidité: {sensor_data['humidity']}% (simulé)")
    print(f"  🪟 Fenêtre: {'ouverte' if sensor_data['window_open'] else 'fermée'} (simulé)")
    print(f"  📅 Hyperplanning: {hp_data['state']} (mock)")
    print(f"  👥 Personnes: 0 (vision désactivée dans ce test)")
    print(f"  🪑 Places libres: {settings.room_capacity}")
    
    # Nettoyage
    sensors.stop()
    hp.stop()
    
    print("\n✓ Intégration OK")
    print("\n💡 Pour tester avec VRAIES données:")
    print("   1. Sur Raspberry Pi")
    print("   2. Brancher DHT22 sur GPIO 4")
    print("   3. Brancher reed switch sur GPIO 17")
    print("   4. Brancher webcam USB")
    print("   5. Lancer: uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print("   6. GET http://raspberry-ip:8000/status\n")


if __name__ == "__main__":
    tests = {
        "models": test_models,
        "sensors": test_sensor_simulation,
        "hyperplanning": test_hyperplanning,
        "integration": test_integration
    }
    
    if len(sys.argv) > 1 and sys.argv[1] in tests:
        tests[sys.argv[1]]()
    else:
        print("Tests disponibles:")
        for name in tests:
            print(f"  python test_backend.py {name}")
        print("\nExécution de tous les tests:\n")
        
        for name, test_func in tests.items():
            try:
                test_func()
            except Exception as e:
                print(f"✗ Erreur {name}: {e}\n")
