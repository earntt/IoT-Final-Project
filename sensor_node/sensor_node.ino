#include <WiFi.h>
#include <PubSubClient.h>
#include "DHT.h"
#include "Wire.h"
#include "MPU6050.h"
#include "esp_log.h"

// ======================= CONFIGURATION =======================
// WiFi credentials with fallback
const char* ssid_primary = "whanwhan";
const char* password_primary = "whanwhanjubjub";
const char* mqtt_server_primary = "172.20.10.2";

const char* ssid_fallback = "Benya_2.4G";
const char* password_fallback = "0868963005";
const char* mqtt_server_fallback = "192.168.1.186";

const int mqtt_port = 1883;

// Active connection details
const char* ssid = ssid_primary;
const char* password = password_primary;
const char* mqtt_server = mqtt_server_primary;

// --- MQTT Topics ---
const char* TOPIC_DATA = "esp32/data";
const char* TOPIC_STATUS = "esp32/status";
const char* TOPIC_CONTROL = "esp32/control";

// --- Pin Definitions ---
#define DHTPIN 4
#define BUTTON_PIN 2
#define SDA_PIN 21
#define SCL_PIN 22
#define DHTTYPE DHT11

// ======================= GLOBAL OBJECTS & VARIABLES =======================
WiFiClient espClient;
PubSubClient client(espClient);
DHT dht(DHTPIN, DHTTYPE);
MPU6050 mpu;

// --- Non-blocking MQTT reconnect ---
long lastReconnectAttempt = 0;

// --- Control variables ---
bool controlEnabled = true;  // Default: enabled

// ======================= SETUP =======================
void setup() {
  esp_log_level_set("*", ESP_LOG_NONE);

  Serial.begin(115200);
  delay(1000);

  connectWiFi();
  initializeSensors();

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
  lastReconnectAttempt = 0;
}

// ======================= MAIN LOOP =======================
void loop() {
  // --- Non-Blocking MQTT Connection Handling ---
  if (!client.connected()) {
    long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      if (reconnectMQTT()) {
        lastReconnectAttempt = 0;
      }
    }
  } else {
    client.loop();
  }

  // Only read and publish data if control is enabled
  if (controlEnabled) {
    float temp = dht.readTemperature();
    float humidity = dht.readHumidity();
    int buttonState = digitalRead(BUTTON_PIN);

    int16_t gx, gy, gz;
    mpu.getRotation(&gx, &gy, &gz);

    float accX = mpu.getAccelerationX() / 16384.0;
    float accY = mpu.getAccelerationY() / 16384.0;
    float accZ = mpu.getAccelerationZ() / 16384.0;
    bool isAbnormal = (abs(accX) >= 1.5 || abs(accY) >= 1.5 || abs(accZ) >= 1.5);

    if (client.connected()) {
      String payload = "{";
      payload += "\"temperature\":" + String(temp, 1) + ",";
      payload += "\"humidity\":" + String(humidity, 1) + ",";
      payload += "\"buttonPressed\":" + String(buttonState == HIGH ? "true" : "false") + ",";
      payload += "\"abnormalMovement\":" + String(isAbnormal ? "true" : "false");
      payload += "}";

      client.publish(TOPIC_DATA, payload.c_str());
      Serial.println("Published data: " + payload);
    }
  }

  delay(1000);
}

// ======================= FUNCTIONS =======================
void initializeSensors() {
  Serial.println("Initializing sensors...");
  dht.begin();
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Wire.begin(SDA_PIN, SCL_PIN);
  mpu.initialize();
  Serial.println(mpu.testConnection() ? "MPU6050 OK" : "MPU6050 FAILED");
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived on topic: ");
  Serial.print(topic);
  Serial.print(". Message: ");
  
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);
  
  // Handle control topic
  if (strcmp(topic, TOPIC_CONTROL) == 0) {
    if (message == "true" || message == "1") {
      controlEnabled = true;
      Serial.println("[CONTROL] Sensor reading ENABLED");
    } else if (message == "false" || message == "0") {
      controlEnabled = false;
      Serial.println("[CONTROL] Sensor reading DISABLED");
    }
  }
}

void connectWiFi() {
  // Try primary WiFi first
  Serial.print("Connecting to primary WiFi: ");
  Serial.println(ssid_primary);
  WiFi.begin(ssid_primary, password_primary);
  
  int attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < 20) {  // 10 seconds timeout
    delay(500);
    Serial.print(".");
    attempt++;
    yield();
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nPrimary WiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    ssid = ssid_primary;
    password = password_primary;
    mqtt_server = mqtt_server_primary;
    return;
  }
  
  // If primary fails, try fallback WiFi
  Serial.println("\nPrimary WiFi failed. Trying fallback...");
  Serial.print("Connecting to fallback WiFi: ");
  Serial.println(ssid_fallback);
  WiFi.disconnect();
  delay(1000);
  WiFi.begin(ssid_fallback, password_fallback);
  
  attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < 20) {  // 10 seconds timeout
    delay(500);
    Serial.print(".");
    attempt++;
    yield();
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nFallback WiFi connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    ssid = ssid_fallback;
    password = password_fallback;
    mqtt_server = mqtt_server_fallback;
    return;
  }
  
  // If both fail, restart ESP32
  Serial.println("\nBoth WiFi connections failed. Restarting...");
  delay(3000);
  ESP.restart();
}

bool reconnectMQTT() {
  Serial.print("Attempting MQTT connection...");
  String clientId = "ESP32Client-" + String(random(0xffff), HEX);
  if (client.connect(clientId.c_str())) {
    Serial.println("connected");
    
    // Subscribe to control topic
    client.subscribe(TOPIC_CONTROL);
    Serial.println("Subscribed to " + String(TOPIC_CONTROL));
    
    // Publish online status
    client.publish(TOPIC_STATUS, "true", true);  // retained message
    Serial.println("Published status: online");
  } else {
    Serial.print("failed, rc=");
    Serial.print(client.state());
    Serial.println(" try again in 5 seconds");
  }
  return client.connected();
}