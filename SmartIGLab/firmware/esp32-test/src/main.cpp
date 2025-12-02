#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ===== CONFIGURATION - À MODIFIER =====
const char* WIFI_SSID = "VOTRE_SSID";                    // SSID Wi-Fi
const char* WIFI_PASS = "VOTRE_PASSWORD";                // Mot de passe
const char* API_URL = "http://172.20.10.8:8000/status"; // IP du Pi + /status

const unsigned long REFRESH_INTERVAL = 5000;  // Test toutes les 5 secondes
const unsigned long WIFI_TIMEOUT = 15000;

// ===== OBJETS =====
HTTPClient http;

// ===== PROTOTYPES =====
void setupWiFi();
void testAPI();
void printStatus(JsonDocument& doc);

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("========================================");
  Serial.println("   SmartIGLab - TEST ESP32 (sans écran)");
  Serial.println("========================================");
  Serial.println();
  
  // LED intégrée pour feedback visuel
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  
  // Connexion Wi-Fi
  setupWiFi();
  
  Serial.println("\n--- Démarrage des tests ---\n");
}

// ===== LOOP =====
void loop() {
  static unsigned long lastTest = 0;
  unsigned long now = millis();
  
  // Vérifier Wi-Fi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[ERREUR] Wi-Fi déconnecté!");
    digitalWrite(LED_BUILTIN, LOW);
    setupWiFi();
    delay(5000);
    return;
  }
  
  // LED clignote = connecté
  digitalWrite(LED_BUILTIN, (millis() / 500) % 2);
  
  // Test API toutes les REFRESH_INTERVAL ms
  if (now - lastTest >= REFRESH_INTERVAL) {
    lastTest = now;
    testAPI();
  }
  
  delay(100);
}

// ===== CONNEXION WI-FI =====
void setupWiFi() {
  Serial.println("┌─────────────────────────────────────┐");
  Serial.println("│     CONNEXION WI-FI                 │");
  Serial.println("└─────────────────────────────────────┘");
  Serial.print("SSID: ");
  Serial.println(WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  Serial.print("Connexion en cours");
  
  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < WIFI_TIMEOUT) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ Wi-Fi connecté avec succès!");
    Serial.print("  IP locale: ");
    Serial.println(WiFi.localIP());
    Serial.print("  Signal (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    Serial.print("  Passerelle: ");
    Serial.println(WiFi.gatewayIP());
    Serial.println();
    
    digitalWrite(LED_BUILTIN, HIGH);
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
  } else {
    Serial.println("\n✗ ÉCHEC connexion Wi-Fi!");
    Serial.println("Vérifiez:");
    Serial.println("  - SSID et mot de passe corrects");
    Serial.println("  - Réseau Wi-Fi actif");
    Serial.println("  - Distance au point d'accès");
    Serial.println();
  }
}

// ===== TEST API =====
void testAPI() {
  Serial.println("┌─────────────────────────────────────┐");
  Serial.println("│     TEST RÉCUPÉRATION /status       │");
  Serial.println("└─────────────────────────────────────┘");
  Serial.print("URL: ");
  Serial.println(API_URL);
  Serial.print("Timestamp: ");
  Serial.println(millis() / 1000);
  Serial.println();
  
  // Début requête
  http.begin(API_URL);
  http.setTimeout(5000);
  
  Serial.println("Envoi requête HTTP GET...");
  unsigned long startTime = millis();
  int httpCode = http.GET();
  unsigned long responseTime = millis() - startTime;
  
  Serial.print("Code HTTP: ");
  Serial.print(httpCode);
  Serial.print(" (temps: ");
  Serial.print(responseTime);
  Serial.println(" ms)");
  
  if (httpCode == 200) {
    Serial.println("✓ Réponse reçue!\n");
    
    String payload = http.getString();
    Serial.println("--- Réponse brute (JSON) ---");
    Serial.println(payload);
    Serial.println("--- Fin réponse ---\n");
    
    // Parser JSON
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);
    
    if (!error) {
      Serial.println("✓ JSON parsé avec succès!\n");
      printStatus(doc);
    } else {
      Serial.print("✗ Erreur parsing JSON: ");
      Serial.println(error.c_str());
    }
    
  } else if (httpCode > 0) {
    Serial.print("✗ Erreur HTTP: ");
    Serial.println(httpCode);
    Serial.println("Vérifiez que le backend est démarré sur le Pi");
  } else {
    Serial.println("✗ Échec connexion HTTP");
    Serial.println("Vérifiez:");
    Serial.println("  - Backend démarré: uvicorn app.main:app");
    Serial.println("  - IP correcte dans API_URL");
    Serial.println("  - Firewall ne bloque pas le port 8000");
    Serial.println("  - Ping fonctionne vers le Pi");
  }
  
  http.end();
  Serial.println("\n========================================\n");
}

// ===== AFFICHAGE STATUT =====
void printStatus(JsonDocument& doc) {
  Serial.println("╔═══════════════════════════════════════╗");
  Serial.println("║     DONNÉES RÉCUPÉRÉES                ║");
  Serial.println("╚═══════════════════════════════════════╝");
  
  // Occupation
  bool occupied = doc["occupied"] | false;
  Serial.print("Statut: ");
  if (occupied) {
    Serial.println("🔴 OCCUPÉ");
  } else {
    Serial.println("🟢 LIBRE");
  }
  
  // Comptage
  int people = doc["people_count"] | 0;
  int free_seats = doc["free_seats"] | 0;
  int capacity = doc["capacity"] | 40;
  
  Serial.println("\n--- Comptage ---");
  Serial.print("Personnes détectées: ");
  Serial.println(people);
  Serial.print("Places libres: ");
  Serial.println(free_seats);
  Serial.print("Capacité totale: ");
  Serial.println(capacity);
  
  // Environnement
  float temp = doc["environment"]["temperature"] | 0.0;
  float hum = doc["environment"]["humidity"] | 0.0;
  bool window = doc["environment"]["window_open"] | false;
  
  Serial.println("\n--- Environnement ---");
  if (temp > 0) {
    Serial.print("Température: ");
    Serial.print(temp, 1);
    Serial.println(" °C");
  } else {
    Serial.println("Température: N/A");
  }
  
  if (hum > 0) {
    Serial.print("Humidité: ");
    Serial.print(hum, 1);
    Serial.println(" %");
  } else {
    Serial.println("Humidité: N/A");
  }
  
  Serial.print("Fenêtre: ");
  Serial.println(window ? "Ouverte" : "Fermée");
  
  // Hyperplanning
  const char* hp_state = doc["hyperplanning"]["state"] | "unknown";
  const char* hp_title = doc["hyperplanning"]["title"] | "";
  
  Serial.println("\n--- Hyperplanning ---");
  Serial.print("État: ");
  Serial.println(hp_state);
  if (strlen(hp_title) > 0) {
    Serial.print("Cours: ");
    Serial.println(hp_title);
  }
  
  // Vision
  float fps = doc["vision_fps"] | 0.0;
  Serial.println("\n--- Vision YOLO ---");
  Serial.print("FPS: ");
  Serial.println(fps, 1);
  
  Serial.println("\n═══════════════════════════════════════");
}
