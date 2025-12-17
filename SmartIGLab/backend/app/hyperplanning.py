"""
SmartIGLab - Client Hyperplanning
==================================
Récupération automatique de l'emploi du temps avec système de fallback:
  1. iCal depuis URL (prioritaire)
  2. Fichier schedule.ical local
  3. Fichier schedule_mock.json (fallback statique)

Thread-safe avec rafraîchissement automatique.
"""

import time
import logging
from typing import Optional
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class HyperplanningClient:
    """
    Client d'emploi du temps avec système triple-fallback
    
    Fonctionne en thread séparé pour ne pas bloquer l'API.
    L'état est partagé de manière thread-safe avec des locks.
    """
    
    def __init__(self, url: str, room_id: str, refresh_interval: float = 300.0):
        """
        Initialise le client Hyperplanning
        
        Args:
            url: URL iCal (si vide, utilise fichier ou JSON)
            room_id: ID de la salle (non utilisé actuellement)
            refresh_interval: Intervalle de rafraîchissement en secondes (défaut: 5min)
        """
        self.url = url
        self.room_id = room_id
        self.refresh_interval = refresh_interval
        
        # État partagé entre threads (protégé par lock)
        self._lock = Lock()
        self._state = "unknown"  # États: "libre", "course_en_cours", "course_prevue", "unknown"
        self._title: Optional[str] = None  # Nom du cours
        self._start_time: Optional[str] = None  # Heure début (HH:MM)
        self._end_time: Optional[str] = None  # Heure fin (HH:MM)
        self._professor: Optional[str] = None  # Nom professeur
        self._last_update: Optional[float] = None  # Timestamp dernière maj
        self._running = False  # État du thread
        
        self._thread: Optional[Thread] = None
    
    def get_status(self) -> dict:
        """
        Retourne l'état actuel de l'emploi du temps
        
        Thread-safe: utilise un lock pour garantir la cohérence.
        
        Returns:
            dict avec state, title, start_time, end_time, professor, last_update
        """
        with self._lock:
            return {
                "state": self._state,
                "title": self._title,
                "start_time": self._start_time,
                "end_time": self._end_time,
                "professor": self._professor,
                "last_update": self._last_update
            }
    
    def _fetch_planning(self):
        """
        Récupère l'emploi du temps avec système de fallback
        
        Priorités:
          1. URL iCal (si configurée)
          2. Fichier schedule.ical (backend/)
          3. Fichier schedule_mock.json (backend/)
        
        Returns:
            dict avec état du cours actuel
        """
        import datetime
        from pathlib import Path
        
        # Heure actuelle
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        
        # 1. Essayer iCal depuis URL
        if self.url:
            try:
                schedule = self._parse_ical_from_url(self.url, now)
                if schedule:
                    return self._find_current_course(schedule, current_time)
            except Exception as e:
                logger.warning(f"Erreur lecture iCal URL: {e}, fallback vers fichier")
        
        # 2. Essayer fichier .ical local
        ical_file = Path(__file__).parent.parent / "schedule.ical"
        if ical_file.exists():
            try:
                schedule = self._parse_ical_from_file(ical_file, now)
                if schedule:
                    return self._find_current_course(schedule, current_time)
            except Exception as e:
                logger.warning(f"Erreur lecture fichier iCal: {e}, fallback vers JSON")
        
        # 3. Fallback: JSON statique
        return self._fetch_from_json(current_time)
    
    def _parse_ical_from_url(self, url: str, date):
        """
        Parse un calendrier iCal depuis une URL
        
        Args:
            url: URL du fichier .ics
            date: Date pour filtrer les événements du jour
        
        Returns:
            Liste d'événements triés par heure de début
        """
        try:
            from icalendar import Calendar
            import requests
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            cal = Calendar.from_ical(response.content)
            return self._extract_events_for_today(cal, date)
        except ImportError:
            logger.error("Module 'icalendar' non installé. Installez-le: pip install icalendar")
            return None
        except Exception as e:
            logger.error(f"Erreur parsing iCal URL: {e}")
            return None
    
    def _parse_ical_from_file(self, filepath, date):
        """
        Parse un calendrier iCal depuis un fichier local
        
        Args:
            filepath: Chemin vers le fichier .ical
            date: Date pour filtrer les événements du jour
        
        Returns:
            Liste d'événements triés par heure de début
        """
        try:
            from icalendar import Calendar
            
            with open(filepath, 'rb') as f:
                cal = Calendar.from_ical(f.read())
            
            return self._extract_events_for_today(cal, date)
        except ImportError:
            logger.error("Module 'icalendar' non installé. Installez-le: pip install icalendar")
            return None
        except Exception as e:
            logger.error(f"Erreur parsing iCal fichier: {e}")
            return None
    
    def _extract_events_for_today(self, cal, date):
        """
        Extrait uniquement les événements du jour depuis un calendrier iCal
        
        Args:
            cal: Objet Calendar d'icalendar
            date: Date pour filtrer (datetime)
        
        Returns:
            Liste d'événements avec title, start, end, professor
        """
        events = []
        today = date.date()
        
        for component in cal.walk():
            if component.name == "VEVENT":
                dtstart = component.get('dtstart')
                dtend = component.get('dtend')
                
                if not dtstart or not dtend:
                    continue
                
                # Convertir en datetime si nécessaire
                start = dtstart.dt
                end = dtend.dt
                
                # Si c'est une date sans heure, skip
                if not hasattr(start, 'hour'):
                    continue
                
                # Vérifier si l'événement est aujourd'hui
                if start.date() == today:
                    events.append({
                        "title": str(component.get('summary', 'Sans titre')),
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M"),
                        "professor": str(component.get('description', '')) or str(component.get('location', ''))
                    })
        
        return sorted(events, key=lambda x: x["start"])
    
    def _find_current_course(self, schedule, current_time):
        """
        Trouve le cours actif dans le planning
        
        Utilise une comparaison en minutes depuis minuit pour éviter
        les erreurs de comparaison de strings ("18:54" vs "18:50").
        
        Args:
            schedule: Liste de cours avec start, end, title, professor
            current_time: Heure actuelle au format "HH:MM"
        
        Returns:
            dict avec state="course_en_cours" ou "libre"
        """
        # Convertir l'heure actuelle en minutes pour comparaison correcte
        current_minutes = self._time_to_minutes(current_time)
        
        for course in schedule:
            start_minutes = self._time_to_minutes(course["start"])
            end_minutes = self._time_to_minutes(course["end"])
            
            if start_minutes <= current_minutes <= end_minutes:
                return {
                    "state": "course_en_cours",
                    "title": course["title"],
                    "start_time": course["start"],
                    "end_time": course["end"],
                    "professor": course.get("professor", "")
                }
        
        # Aucun cours maintenant
        return {
            "state": "libre",
            "title": None,
            "start_time": None,
            "end_time": None,
            "professor": None
        }
    
    def _time_to_minutes(self, time_str):
        """
        Convertit HH:MM en minutes depuis minuit
        
        Permet une comparaison numérique correcte des heures.
        Exemple: "18:54" -> 1134, "18:50" -> 1130
        
        Args:
            time_str: Heure au format "HH:MM"
        
        Returns:
            Nombre de minutes depuis minuit (int)
        """
        try:
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        except:
            return 0
    
    def _fetch_from_json(self, current_time):
        """
        Fallback final: lecture depuis JSON statique
        
        Lit schedule_mock.json pour avoir un emploi du temps
        même si iCal n'est pas disponible.
        
        Args:
            current_time: Heure actuelle "HH:MM"
        
        Returns:
            dict avec état du cours actuel
        """
        import json
        from pathlib import Path
        
        schedule_file = Path(__file__).parent.parent / "schedule_mock.json"
        
        if not schedule_file.exists():
            logger.warning("schedule_mock.json introuvable, retour état libre")
            return {
                "state": "libre",
                "title": None,
                "start_time": None,
                "end_time": None,
                "professor": None
            }
        
        try:
            with open(schedule_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convertir temps pour comparaison correcte
            schedule = [{"title": c["title"], "start": c["start"], "end": c["end"], 
                        "professor": c.get("professor", "")} 
                       for c in data.get("schedule", [])]
            
            return self._find_current_course(schedule, current_time)
            
        except Exception as e:
            logger.error(f"Erreur lecture JSON: {e}")
            return {
                "state": "unknown",
                "title": None,
                "start_time": None,
                "end_time": None,
                "professor": None
            }
    
    def _update_state(self, data: dict):
        """
        Met à jour l'état interne de manière thread-safe
        
        Args:
            data: dict avec state, title, start_time, end_time, professor
        """
        with self._lock:
            self._state = data.get("state", "unknown")
            self._title = data.get("title")
            self._start_time = data.get("start_time")
            self._end_time = data.get("end_time")
            self._professor = data.get("professor")
            self._last_update = time.time()
    
    def _run_loop(self):
        """
        Boucle principale du thread de rafraîchissement
        
        Récupère l'emploi du temps à intervalle régulier.
        Tourne en tâche de fond (daemon thread).
        """
        logger.info(f"Démarrage Hyperplanning client (intervalle: {self.refresh_interval}s)")
        
        while self._running:
            try:
                data = self._fetch_planning()
                self._update_state(data)
                logger.info(f"Hyperplanning: état={data['state']}")
            except Exception as e:
                logger.error(f"Erreur récupération planning: {e}")
            
            time.sleep(self.refresh_interval)
        
        logger.info("Boucle Hyperplanning arrêtée")
    
    def start(self):
        """
        Démarre le thread de rafraîchissement
        
        Lance une boucle en arrière-plan qui récupère l'emploi
        du temps à intervalles réguliers.
        """
        if self._running:
            logger.warning("Client Hyperplanning déjà en cours")
            return
        
        if not self.url:
            logger.warning("URL Hyperplanning non configurée - mode mock")
        
        self._running = True
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Client Hyperplanning démarré")
    
    def stop(self):
        """
        Arrête proprement le thread de rafraîchissement
        
        Appelé lors de l'arrêt de l'application.
        """
        if not self._running:
            return
        
        logger.info("Arrêt client Hyperplanning...")
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
