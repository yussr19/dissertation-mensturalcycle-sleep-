
#include "config.h"

#include <WiFiNINA.h>
#include <PubSubClient.h>
#include <Servo.h>
#include <Stepper.h>
#include <ArduinoJson.h>

// ============================================================
// WIFI / MQTT
// ============================================================
// Credentials live in config.h, which is gitignored.
// Copy config.example.h to config.h and fill in your values.

const char* MQTT_BROKER = "mqtt.cetools.org";
const int   MQTT_PORT = 1884;

const char* TOPIC = "student/CASA0022/yussr/sleepquality";


// ============================================================
// HARDWARE
// ============================================================

const int SERVO_PIN = 6;
const int STEPS_PER_REV = 2048;

Stepper disc(STEPS_PER_REV, 8, 10, 9, 11);
Servo penArm;


// ============================================================
// SERVO CALIBRATION
// ============================================================

const int ANGLE_Q1  = 20;   // sleep quality 1  = inner ring
const int ANGLE_Q10 = 160;  // sleep quality 10 = outer ring


// ============================================================
// TIMING
// ============================================================

const unsigned long REPLAY_INTERVAL_MS = 600000UL;  // 10 minutes
unsigned long lastReplay = 0;


// ============================================================
// DATA
// ============================================================
// No synthetic data. These values are filled from MQTT.

int  history[28] = {0};
bool receivedDay[28] = {false};
int  receivedCount = 0;
int  latestQuality = 0;
int  latestCycleDay = 0;


// ============================================================
// NETWORK OBJECTS
// ============================================================

WiFiClient wifi;
PubSubClient mqtt(wifi);


// ============================================================
// SERVO
// ============================================================

int currentAngle = -1;

int qualityToAngle(int q) {
  q = constrain(q, 1, 10);
  return map(q, 1, 10, ANGLE_Q1, ANGLE_Q10);
}

void moveServoSlowly(int targetAngle, int stepDelayMs) {

  if (currentAngle == -1) {
    penArm.write(targetAngle);
    currentAngle = targetAngle;
    return;
  }

  int step = (targetAngle > currentAngle) ? 1 : -1;

  while (currentAngle != targetAngle) {
    currentAngle += step;
    penArm.write(currentAngle);
    delay(stepDelayMs);
  }
}


// ============================================================
// PRINT CURRENT HISTORY
// ============================================================

void printHistory() {

  Serial.println();
  Serial.println("Current 28-day history:");

  for (int i = 0; i < 28; i++) {
    Serial.print("Day ");
    Serial.print(i + 1);
    Serial.print(": ");
    if (receivedDay[i]) {
      Serial.println(history[i]);
    } else {
      Serial.println("-");
    }
  }

  Serial.print("Days received: ");
  Serial.print(receivedCount);
  Serial.println("/28");
  Serial.println();
}


// ============================================================
// MQTT CALLBACK
// ============================================================

void mqttCallback(char* topic, byte* payload, unsigned int len) {

  StaticJsonDocument<128> doc;

  DeserializationError error = deserializeJson(doc, payload, len);

  if (error) {
    Serial.print("JSON error: ");
    Serial.println(error.c_str());
    return;
  }

  if (!doc.containsKey("quality") || !doc.containsKey("cycle_day")) {
    Serial.println("MQTT message missing quality or cycle_day");
    return;
  }

  int q   = doc["quality"];
  int day = doc["cycle_day"];

  if (q < 1 || q > 10) {
    Serial.print("Invalid quality: ");
    Serial.println(q);
    return;
  }

  if (day < 1 || day > 28) {
    Serial.print("Invalid cycle day: ");
    Serial.println(day);
    return;
  }

  int index = day - 1;
  history[index] = q;

  if (!receivedDay[index]) {
    receivedDay[index] = true;
    receivedCount++;
  }

  latestQuality  = q;
  latestCycleDay = day;

  Serial.print("Received cycle day ");
  Serial.print(day);
  Serial.print(" | sleep quality ");
  Serial.println(q);

  moveServoSlowly(qualityToAngle(q), 20);

  if (receivedCount == 28) {
    Serial.println();
    Serial.println("FULL 28-DAY DATASET RECEIVED");
    printHistory();
  }
}


// ============================================================
// WIFI CONNECTION
// ============================================================

void connectWiFi() {

  const char* ssids[]  = { WIFI_SSID_1, WIFI_SSID_2 };
  const char* passes[] = { WIFI_PASS_1, WIFI_PASS_2 };

  for (int i = 0; i < 2 && WiFi.status() != WL_CONNECTED; i++) {

    Serial.print("WiFi try: ");
    Serial.println(ssids[i]);

    WiFi.begin(ssids[i], passes[i]);

    unsigned long start = millis();

    while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
      delay(500);
    }
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi connection failed");
  }
}


// ============================================================
// MQTT CONNECTION
// ============================================================

void connectMQTT() {

  if (WiFi.status() != WL_CONNECTED) return;

  while (!mqtt.connected()) {

    Serial.println("Connecting to MQTT...");

    if (mqtt.connect("luna-recorder", MQTT_USER, MQTT_PASSWD)) {

      Serial.println("MQTT connected");
      mqtt.subscribe(TOPIC);
      Serial.print("Subscribed to: ");
      Serial.println(TOPIC);

    } else {

      Serial.print("MQTT failed, state=");
      Serial.println(mqtt.state());
      delay(3000);
    }
  }
}


// ============================================================
// REPLAY THE RECEIVED 28-DAY DATA
// ============================================================

void replayHistory() {

  if (receivedCount == 0) {
    Serial.println("No data received yet.");
    return;
  }

  Serial.println();
  Serial.println("Starting received-data replay...");

  for (int day = 0; day < 28; day++) {

    if (!receivedDay[day]) continue;

    int q = history[day];

    Serial.print("Replay day ");
    Serial.print(day + 1);
    Serial.print(" quality ");
    Serial.println(q);

    // Move pen radially
    moveServoSlowly(qualityToAngle(q), 15);

    // Advance disc one cycle day: 2048 / 28 = ~73 steps
    int stepsPerDay = STEPS_PER_REV / 28;
    disc.step(stepsPerDay);

    delay(400);
  }

  Serial.println("Replay complete.");

  if (latestQuality >= 1) {
    moveServoSlowly(qualityToAngle(latestQuality), 15);
  }
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(9600);
  delay(1500);

  Serial.println();
  Serial.println("Luna recorder starting");

  penArm.attach(SERVO_PIN);
  disc.setSpeed(5);

  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(mqttCallback);

  connectWiFi();
  connectMQTT();

  lastReplay = millis();

  Serial.println("Waiting for sleep-quality data...");
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (WiFi.status() == WL_CONNECTED && !mqtt.connected()) {
    connectMQTT();
  }

  mqtt.loop();

  unsigned long now = millis();

  if (now - lastReplay >= REPLAY_INTERVAL_MS) {
    replayHistory();
    // replayHistory() blocks, so reset the timer after it returns
    lastReplay = millis();
  }
}
