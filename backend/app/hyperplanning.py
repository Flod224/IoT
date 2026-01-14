"""
SmartIGLab - Client Hyperplanning
==================================
Récupération automatique de l'emploi du temps.
Thread-safe avec rafraîchissement automatique.

Sources:
  - ICS: Edt_Ho_IGLab.ics (calendrier réel)
  - JSON: schedule_mock.json (mode démo)
"""

import time
import logging
from typing import Optional
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class HyperplanningClient:
    """
    Client d'emploi du temps SmartIGLab
    
    Fonctionne en thread séparé pour ne pas bloquer l'API.
    L'état est partagé de manière thread-safe avec des locks.
    
    Sources:
      - ICS: Edt_Ho_IGLab.ics (calendrier réel)
      - JSON: schedule_mock.json (mode démo)
    """
    
    def __init__(self, use_ics: bool = False, refresh_interval: float = 60.0):
        """
        Initialise le client Hyperplanning
        
        Args:
            use_ics: False=JSON, True=ICS
            refresh_interval: Intervalle de rafraîchissement en secondes (défaut: 60s)
        """
      
        self.use_ics = use_ics
        self.refresh_interval = refresh_interval
        
        # État partagé entre threads (protégé par lock)
        self._lock = Lock()
        self._state = "unknown"
        self._title: Optional[str] = None
        self._start_time: Optional[str] = None
        self._end_time: Optional[str] = None
        self._professor: Optional[str] = None
        self._formation: Optional[str] = None
        self._type: Optional[str] = None
        self._last_update: Optional[float] = None
        self._running = False
        
        self._thread: Optional[Thread] = None
    
    def get_status(self) -> dict:
        """
        Retourne l'état actuel de l'emploi du temps (thread-safe)
        
        Returns:
            dict avec state, title, start_time, end_time, professor, formation, type, last_update
        """
        with self._lock:
            return {
                "state": self._state,
                "title": self._title,
                "start_time": self._start_time,
                "end_time": self._end_time,
                "professor": self._professor,
                "formation": self._formation,
                "type": self._type,
                "last_update": self._last_update
            }
    
    def _fetch_planning(self):
        """
        Récupère l'emploi du temps selon le mode configuré
        
        Mode ICS: Lit UNIQUEMENT Edt_Ho_IGLab.ics
        Mode JSON: Lit UNIQUEMENT schedule_mock.json
        
        Returns:
            dict avec état du cours actuel ou libre si aucune donnée
        """
        import datetime
        from pathlib import Path
        
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        
        if self.use_ics:
            # Mode ICS uniquement
            ical_file = Path(__file__).parent.parent / "Edt_Ho_IGLab.ics"
            if not ical_file.exists():
                logger.error("Fichier ICS introuvable: Edt_Ho_IGLab.ics")
                return self._empty_state()
            
            try:
                schedule = self._parse_ical_from_file(ical_file, now)
                if schedule is None or len(schedule) == 0:
                    logger.info("Aucun cours aujourd'hui (ICS)")
                    return self._empty_state()
                return self._find_current_course(schedule, current_time)
            except Exception as e:
                logger.error(f"Erreur lecture ICS: {e}")
                return self._empty_state()
        else:
            # Mode JSON uniquement
            return self._fetch_from_json(current_time)
    
    def _empty_state(self):
        """Retourne un état libre sans données"""
        return {
            "state": "libre",
            "title": None,
            "start_time": None,
            "end_time": None,
            "professor": None,
            "formation": None,
            "type": None
        }
    
    def _parse_ical_from_file(self, filepath, date):
        """
        Parse un calendrier iCal depuis un fichier local
        
        Args:
            filepath: Chemin vers le fichier .ics
            date: Date pour filtrer les événements du jour
        
        Returns:
            Liste d'événements triés par heure de début ou None si erreur
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
            Liste d'événements avec title, start, end, professor, formation, type
        """
        import re
        events = []
        today = date.date()
        
        for component in cal.walk():
            if component.name == "VEVENT":
                dtstart = component.get('dtstart')
                dtend = component.get('dtend')
                
                if not dtstart or not dtend:
                    continue
                
                start = dtstart.dt
                end = dtend.dt
                
                # Si c'est une date sans heure, skip
                if not hasattr(start, 'hour'):
                    continue
                
                # Vérifier si l'événement est aujourd'hui
                if start.date() == today:
                    description = str(component.get('description', ''))
                    
                    # Extraire le nom du cours
                    title = 'Sans titre'
                    title_match = re.search(r'(?:Aa|aa|AA)\s*:\s*([^\n]+)', description)
                    if title_match:
                        title = title_match.group(1).strip()
                    
                    # Extraire l'enseignant
                    professor = ''
                    prof_match = re.search(r'(?:Enseignants?|Teachers?|Professors?)\s*:\s*([^\n]+)', description, re.IGNORECASE)
                    if prof_match:
                        professor = prof_match.group(1).strip()
                    
                    # Extraire les formations
                    formation = ''
                    form_match = re.search(r'(?:Formations?|Groups?)\s*:\s*([^\n]+)', description, re.IGNORECASE)
                    if form_match:
                        formation = form_match.group(1).strip()
                    
                    # Extraire le type
                    course_type = ''
                    type_match = re.search(r'(?:Type|Kind)\s*:\s*([^\n]+)', description, re.IGNORECASE)
                    if type_match:
                        course_type = type_match.group(1).strip()
                    
                    events.append({
                        "title": title,
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M"),
                        "professor": professor,
                        "formation": formation,
                        "type": course_type
                    })
        
        return sorted(events, key=lambda x: x["start"])
    
    def _find_current_course(self, schedule, current_time):
        """
        Trouve le cours actif dans le planning
        
        Args:
            schedule: Liste de cours avec start, end, title, professor, formation, type
            current_time: Heure actuelle au format "HH:MM"
        
        Returns:
            dict avec state="course_en_cours" ou "libre"
        """
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
                    "professor": course.get("professor", ""),
                    "formation": course.get("formation", ""),
                    "type": course.get("type", "")
                }
        
        # Aucun cours maintenant
        return self._empty_state()
    
    def _time_to_minutes(self, time_str):
        """
        Convertit HH:MM en minutes depuis minuit
        
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
        Lecture depuis JSON statique (mode démo)
        
        Args:
            current_time: Heure actuelle "HH:MM"
        
        Returns:
            dict avec état du cours actuel
        """
        import json
        from pathlib import Path
        
        schedule_file = Path(__file__).parent.parent / "schedule_mock.json"
        
        if not schedule_file.exists():
            logger.error("schedule_mock.json introuvable")
            return self._empty_state()
        
        try:
            with open(schedule_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            schedule = [{"title": c["title"], "start": c["start"], "end": c["end"], 
                        "professor": c.get("professor", ""),
                        "formation": c.get("formation", ""),
                        "type": c.get("type", "")} 
                       for c in data.get("schedule", [])]
            
            return self._find_current_course(schedule, current_time)
            
        except Exception as e:
            logger.error(f"Erreur lecture JSON: {e}")
            return self._empty_state()
    
    def _update_state(self, data: dict):
        """
        Met à jour l'état interne de manière thread-safe
        
        Args:
            data: dict avec state, title, start_time, end_time, professor, formation, type
        """
        with self._lock:
            self._state = data.get("state", "unknown")
            self._title = data.get("title")
            self._start_time = data.get("start_time")
            self._end_time = data.get("end_time")
            self._professor = data.get("professor")
            self._formation = data.get("formation")
            self._type = data.get("type")
            self._last_update = time.time()
    
    def _run_loop(self):
        """
        Boucle principale du thread de rafraîchissement
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
        """
        if self._running:
            logger.warning("Client Hyperplanning déjà en cours")
            return
        
        mode = "ICS" if self.use_ics else "JSON"
        logger.info(f"Hyperplanning mode: {mode}")
        
        self._running = True
        self._thread = Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Client Hyperplanning démarré")
    
    def stop(self):
        """
        Arrête proprement le thread de rafraîchissement
        """
        if not self._running:
            return
        
        logger.info("Arrêt client Hyperplanning...")
        self._running = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
