#include <WiFi.h>
#include <PubSubClient.h>
#include "DHT.h"
#include "Wire.h"
#include "MPU6050.h"
#include "esp_log.h"

// ======================= CONFIGURATION =======================
const char* ssid = "whanwhan";
const char* password = "whanwhanjubjub";
const char* mqtt_server = "172.20.10.3";
const int mqtt_port = 1883;

// --- Pin Definitions ---
#define DHTPIN 12
#define BUTTON_PIN 13
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

// ======================= SETUP =======================
void setup() {
  esp_log_level_set("*", ESP_LOG_NONE);

  Serial.begin(115200);
  delay(1000);

  connectWiFi();
  initializeSensors();

  client.setServer(mqtt_server, mqtt_port);
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

    client.publish("esp32/data", payload);

    Serial.println("Published data: " + payload);
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

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    yield();
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

bool reconnectMQTT() {
  Serial.print("Attempting MQTT connection...");
  String clientId = "ESP32Client-" + String(random(0xffff), HEX);
  if (client.connect(clientId.c_str())) {
    Serial.println("connected");
  } else {
    Serial.print("failed, rc=");
    Serial.print(client.state());
    Serial.println(" try again in 5 seconds");
  }
  return client.connected();
}