"""
Script de test du backend (hors Raspberry Pi)
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
    """Test du module capteurs en mode simulation"""
    print("=== Test Sensors (simulation) ===")
    from app.sensors import SensorReader
    
    reader = SensorReader(dht_pin=4, reed_pin=17, interval=2.0)
    reader.start()
    
    time.sleep(5)
    
    data = reader.get_data()
    print(f"Température: {data['temperature']}°C")
    print(f"Humidité: {data['humidity']}%")
    print(f"Fenêtre: {'ouverte' if data['window_open'] else 'fermée'}")
    
    reader.stop()
    print("✓ Sensors OK\n")


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
    """Test d'intégration (sans vision)"""
    print("=== Test Intégration ===")
    import os
    os.environ["VISION_ENABLED"] = "False"
    
    from app.config import settings
    from app.sensors import SensorReader
    from app.hyperplanning import HyperplanningClient
    
    # Démarrer services
    sensors = SensorReader(settings.dht22_pin, settings.reed_switch_pin, 2.0)
    sensors.start()
    
    hp = HyperplanningClient("", "iglab", 5.0)
    hp.start()
    
    # Simuler agrégation
    time.sleep(3)
    
    sensor_data = sensors.get_data()
    hp_data = hp.get_status()
    
    print("\nDonnées agrégées:")
    print(f"  Capteurs: T={sensor_data['temperature']}°C, RH={sensor_data['humidity']}%")
    print(f"  Hyperplanning: {hp_data['state']}")
    print(f"  Personnes: 0 (vision désactivée)")
    
    # Nettoyage
    sensors.stop()
    hp.stop()
    
    print("✓ Intégration OK\n")


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
