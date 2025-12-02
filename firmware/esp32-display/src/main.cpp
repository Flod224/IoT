#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>

// ===== CONFIGURATION =====
const char* WIFI_SSID = "VOTRE_SSID";           // SSID du Pi en mode AP
const char* WIFI_PASS = "VOTRE_PASSWORD";       // Mot de passe Wi-Fi
const char* API_URL = "http://192.168.1.10:8000/status";  // IP du Raspberry Pi

const unsigned long REFRESH_INTERVAL = 2000;    // Rafraîchissement toutes les 2 secondes
const unsigned long WIFI_TIMEOUT = 10000;       // Timeout connexion Wi-Fi

// ===== OBJETS =====
TFT_eSPI tft = TFT_eSPI();
HTTPClient http;

// ===== COULEURS =====
#define COLOR_BG       0x0000   // Noir
#define COLOR_LIBRE    0x07E0   // Vert
#define COLOR_OCCUPE   0xF800   // Rouge
#define COLOR_TEXT     0xFFFF   // Blanc
#define COLOR_GRAY     0x7BEF   // Gris

// ===== ÉTAT =====
struct RoomStatus {
  bool occupied;
  int people_count;
  int free_seats;
  int capacity;
  float temperature;
  float humidity;
  bool window_open;
  String hp_state;
  float fps;
  bool data_valid;
  unsigned long last_update;
};

RoomStatus currentStatus;

// ===== PROTOTYPES =====
void setupWiFi();
void fetchStatus();
void displayStatus();
void displayError(const char* message);
void displayConnecting();

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(100);
  
  Serial.println("=== SmartIGLab Display ===");
  
  // Initialiser écran
  tft.init();
  tft.setRotation(0);  // Portrait
  tft.fillScreen(COLOR_BG);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  
  // Message de démarrage
  tft.setTextSize(2);
  tft.setCursor(20, 100);
  tft.println("SmartIGLab");
  tft.setCursor(20, 140);
  tft.setTextSize(1);
  tft.println("Initialisation...");
  
  // Connecter au Wi-Fi
  setupWiFi();
  
  // État initial
  currentStatus.data_valid = false;
  currentStatus.last_update = 0;
  
  Serial.println("Setup terminé");
}

// ===== LOOP =====
void loop() {
  static unsigned long lastFetch = 0;
  unsigned long now = millis();
  
  // Vérifier connexion Wi-Fi
  if (WiFi.status() != WL_CONNECTED) {
    displayError("Wi-Fi deconnecte");
    Serial.println("Wi-Fi perdu, reconnexion...");
    setupWiFi();
    delay(5000);
    return;
  }
  
  // Récupérer données toutes les REFRESH_INTERVAL ms
  if (now - lastFetch >= REFRESH_INTERVAL) {
    lastFetch = now;
    fetchStatus();
    displayStatus();
  }
  
  delay(100);
}

// ===== CONNEXION WI-FI =====
void setupWiFi() {
  Serial.print("Connexion Wi-Fi à: ");
  Serial.println(WIFI_SSID);
  
  displayConnecting();
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < WIFI_TIMEOUT) {
    delay(500);
    Serial.print(".");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWi-Fi connecté!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    
    tft.fillScreen(COLOR_BG);
    tft.setTextSize(1);
    tft.setCursor(20, 150);
    tft.setTextColor(COLOR_LIBRE, COLOR_BG);
    tft.println("Wi-Fi OK!");
    delay(1000);
  } else {
    Serial.println("\nÉchec connexion Wi-Fi");
    displayError("Echec Wi-Fi");
    delay(3000);
  }
}

// ===== RÉCUPÉRATION DONNÉES API =====
void fetchStatus() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  
  Serial.println("Récupération /status...");
  
  http.begin(API_URL);
  http.setTimeout(5000);
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    String payload = http.getString();
    Serial.println("Réponse reçue:");
    Serial.println(payload);
    
    // Parser JSON
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      currentStatus.occupied = doc["occupied"] | false;
      currentStatus.people_count = doc["people_count"] | 0;
      currentStatus.free_seats = doc["free_seats"] | 0;
      currentStatus.capacity = doc["capacity"] | 40;
      currentStatus.fps = doc["vision_fps"] | 0.0;
      
      // Environnement
      currentStatus.temperature = doc["environment"]["temperature"] | 0.0;
      currentStatus.humidity = doc["environment"]["humidity"] | 0.0;
      currentStatus.window_open = doc["environment"]["window_open"] | false;
      
      // Hyperplanning
      currentStatus.hp_state = doc["hyperplanning"]["state"] | "unknown";
      
      currentStatus.data_valid = true;
      currentStatus.last_update = millis();
      
      Serial.println("Données parsées avec succès");
    } else {
      Serial.print("Erreur parsing JSON: ");
      Serial.println(error.c_str());
      currentStatus.data_valid = false;
    }
  } else {
    Serial.print("Erreur HTTP: ");
    Serial.println(httpCode);
    currentStatus.data_valid = false;
  }
  
  http.end();
}

// ===== AFFICHAGE STATUT =====
void displayStatus() {
  if (!currentStatus.data_valid) {
    displayError("Donnees invalides");
    return;
  }
  
  tft.fillScreen(COLOR_BG);
  
  // ===== EN-TÊTE =====
  tft.setTextSize(2);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(20, 10);
  tft.println("SmartIGLab");
  
  // ===== STATUT PRINCIPAL =====
  int yPos = 60;
  
  // État occupé/libre
  tft.setTextSize(3);
  if (currentStatus.occupied) {
    tft.setTextColor(COLOR_OCCUPE, COLOR_BG);
    tft.setCursor(30, yPos);
    tft.println("OCCUPE");
  } else {
    tft.setTextColor(COLOR_LIBRE, COLOR_BG);
    tft.setCursor(40, yPos);
    tft.println("LIBRE");
  }
  
  yPos += 50;
  
  // ===== COMPTAGE PERSONNES =====
  tft.setTextSize(2);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  
  tft.setCursor(20, yPos);
  tft.print("Personnes: ");
  tft.println(currentStatus.people_count);
  yPos += 30;
  
  tft.setCursor(20, yPos);
  tft.print("Places libres: ");
  tft.println(currentStatus.free_seats);
  yPos += 40;
  
  // ===== ENVIRONNEMENT =====
  tft.setTextSize(1);
  tft.setTextColor(COLOR_GRAY, COLOR_BG);
  
  // Température
  tft.setCursor(20, yPos);
  tft.print("Temperature: ");
  if (currentStatus.temperature > 0) {
    tft.print(currentStatus.temperature, 1);
    tft.println(" C");
  } else {
    tft.println("--");
  }
  yPos += 20;
  
  // Humidité
  tft.setCursor(20, yPos);
  tft.print("Humidite: ");
  if (currentStatus.humidity > 0) {
    tft.print(currentStatus.humidity, 1);
    tft.println(" %");
  } else {
    tft.println("--");
  }
  yPos += 20;
  
  // Fenêtre
  tft.setCursor(20, yPos);
  tft.print("Fenetre: ");
  tft.println(currentStatus.window_open ? "Ouverte" : "Fermee");
  yPos += 30;
  
  // ===== HYPERPLANNING =====
  tft.setCursor(20, yPos);
  tft.print("Planning: ");
  if (currentStatus.hp_state == "course_en_cours") {
    tft.println("Cours en cours");
  } else if (currentStatus.hp_state == "libre") {
    tft.println("Libre");
  } else {
    tft.println("Inconnu");
  }
  yPos += 30;
  
  // ===== FOOTER =====
  tft.setTextSize(1);
  tft.setTextColor(COLOR_GRAY, COLOR_BG);
  tft.setCursor(20, 300);
  tft.print("FPS: ");
  tft.print(currentStatus.fps, 1);
  
  // Temps depuis dernière MAJ
  unsigned long secSinceUpdate = (millis() - currentStatus.last_update) / 1000;
  tft.setCursor(120, 300);
  tft.print(secSinceUpdate);
  tft.print("s");
}

// ===== AFFICHAGE ERREUR =====
void displayError(const char* message) {
  tft.fillScreen(COLOR_BG);
  tft.setTextSize(2);
  tft.setTextColor(COLOR_OCCUPE, COLOR_BG);
  tft.setCursor(20, 140);
  tft.println("ERREUR");
  
  tft.setTextSize(1);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(20, 180);
  tft.println(message);
}

// ===== AFFICHAGE CONNEXION =====
void displayConnecting() {
  tft.fillScreen(COLOR_BG);
  tft.setTextSize(2);
  tft.setTextColor(COLOR_TEXT, COLOR_BG);
  tft.setCursor(20, 140);
  tft.println("Connexion...");
}
