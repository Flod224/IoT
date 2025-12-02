#!/usr/bin/env python3
"""
Exemple d'utilisation du module PeopleCounter
"""

import time
from people_counter import PeopleCounter, Config, load_env_file

def example_background():
    """Exemple: compteur en arrière-plan"""
    print("=== Mode arrière-plan ===")
    
    load_env_file()
    config = Config()
    counter = PeopleCounter(config)
    
    # Démarrer en background
    counter.start()
    
    try:
        # Lire périodiquement l'état
        for i in range(20):
            time.sleep(1)
            status = counter.get_status()
            print(f"[{i+1}] Personnes: {status['people_count']}, "
                  f"Places libres: {status['free_seats']}, "
                  f"FPS: {status['fps']}")
    
    except KeyboardInterrupt:
        print("\nInterruption...")
    finally:
        counter.stop()
        print("Compteur arrêté")


def example_properties():
    """Exemple: accès aux propriétés"""
    print("=== Accès aux propriétés ===")
    
    load_env_file()
    config = Config()
    counter = PeopleCounter(config)
    
    counter.start()
    
    try:
        for i in range(10):
            time.sleep(1)
            print(f"[{i+1}] {counter.people_count} personnes @ {counter.fps:.1f} FPS")
    
    except KeyboardInterrupt:
        pass
    finally:
        counter.stop()


def example_blocking():
    """Exemple: mode bloquant pour CLI"""
    print("=== Mode bloquant (Ctrl+C pour arrêter) ===")
    
    load_env_file()
    config = Config()
    counter = PeopleCounter(config)
    
    # Bloque jusqu'à Ctrl+C
    counter.run_blocking()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "blocking":
        example_blocking()
    elif len(sys.argv) > 1 and sys.argv[1] == "props":
        example_properties()
    else:
        example_background()
