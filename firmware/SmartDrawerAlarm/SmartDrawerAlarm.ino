#include <Arduino.h>

#include "config.h"
#include "pins.h"
#include "event_log.h"
#include "ldr_sensor.h"
#include "accel_sensor.h"
#include "alarm_buzzer.h"
#include "state_machine.h"
#include "ble_service.h"

EventLogger logger;
LdrSensorArray ldrSensors;
MotionSensor motionSensor;
BuzzerController buzzer;
SecurityStateMachine security;
BleCommandService ble;

String currentPin = DEFAULT_PIN;
uint32_t lastSensorPoll = 0;
uint32_t lastStatusNotify = 0;

String buildStatusLine() {
  String line = "STATUS ";
  line += security.stateText();
  line += " reason=";
  line += security.reasonText();
  line += " ble=";
  line += ble.connected() ? "connected" : "advertising";
  line += " accel=";
  line += motionSensor.sensorName();
  if (motionSensor.address() != 0) {
    line += " who=0x";
    if (motionSensor.whoAmI() < 16) {
      line += "0";
    }
    line += String(motionSensor.whoAmI(), HEX);
  }
  line += " ";
  line += ldrSensors.summary();
  return line;
}

void publishLog(const String &message) {
  logger.add(message);
  ble.notifyLog(logger.latest());
}

bool checkPin(const String &pin) {
  return pin == currentPin;
}

String tokenAt(const String &input, uint8_t index) {
  int start = 0;
  uint8_t current = 0;
  while (start < input.length()) {
    while (start < input.length() && input[start] == ' ') {
      start++;
    }
    int end = input.indexOf(' ', start);
    if (end == -1) {
      end = input.length();
    }
    if (current == index) {
      return input.substring(start, end);
    }
    current++;
    start = end + 1;
  }
  return "";
}

void handleCommand(const String &rawCommand) {
  String command = rawCommand;
  command.trim();
  command.toUpperCase();

  String verb = tokenAt(command, 0);
  String response;

  if (verb == "ARM") {
    String pin = tokenAt(command, 1);
    if (!checkPin(pin)) {
      response = "ERR WRONG_PIN";
      publishLog("COMMAND ARM wrong_pin");
    } else {
      ldrSensors.calibrate();
      motionSensor.calibrate();
      security.arm();
      buzzer.stop();
      response = "OK ARMED";
      publishLog("ARMED");
    }
  } else if (verb == "DISARM") {
    String pin = tokenAt(command, 1);
    if (!checkPin(pin)) {
      response = "ERR WRONG_PIN";
      publishLog("COMMAND DISARM wrong_pin");
    } else {
      security.disarm();
      buzzer.stop();
      response = "OK DISARMED";
      publishLog("DISARMED");
    }
  } else if (verb == "STATUS") {
    response = buildStatusLine();
  } else if (verb == "PING") {
    response = "PONG";
  } else if (verb == "GET_LOG") {
    response = logger.dump();
  } else if (verb == "CALIBRATE_LIGHT") {
    ldrSensors.calibrate();
    response = "OK CALIBRATED_LIGHT ";
    response += ldrSensors.summary();
    publishLog("CALIBRATED_LIGHT");
  } else if (verb == "CALIBRATE_MOTION") {
    motionSensor.calibrate();
    response = "OK CALIBRATED_MOTION ";
    response += motionSensor.i2cReport();
    publishLog("CALIBRATED_MOTION");
  } else if (verb == "CHANGE_PIN") {
    String oldPin = tokenAt(command, 1);
    String newPin = tokenAt(command, 2);
    if (!checkPin(oldPin)) {
      response = "ERR WRONG_PIN";
      publishLog("COMMAND CHANGE_PIN wrong_pin");
    } else if (newPin.length() < 4 || newPin.length() > 8) {
      response = "ERR INVALID_PIN";
    } else {
      currentPin = newPin;
      response = "OK PIN_CHANGED";
      publishLog("PIN_CHANGED");
    }
  } else {
    response = "ERR INVALID_COMMAND";
    publishLog("COMMAND invalid " + rawCommand);
  }

  ble.notifyStatus(response);
  Serial.println("[BLE] " + response);
}

void pollSensors() {
  if (!security.isArmed()) {
    return;
  }

  LdrReading light = ldrSensors.read();
  AccelReading motion = motionSensor.read();

  if (security.trigger(light.lightDetected, motion.motionDetected)) {
    buzzer.setAlarmActive(true);
    String reason = "ALARM ";
    reason += security.reasonText();
    reason += " lightVotes=";
    reason += light.voteCount;
    if (motion.valid) {
      reason += " motionDelta=";
      reason += String(motion.delta, 1);
    } else {
      reason += " motion=unavailable";
    }
    publishLog(reason);
    ble.notifyStatus(reason);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  delay(200);
  Serial.println();
  Serial.println("Smart Drawer Anti-Theft System boot");

  logger.begin();
  buzzer.begin();
  ldrSensors.begin();
  motionSensor.begin();

  publishLog(motionSensor.i2cReport());
  publishLog(ldrSensors.summary());

  ble.begin(handleCommand);
  ble.notifyStatus(buildStatusLine());
  publishLog("BLE advertising SmartDrawerAlarm");
}

void loop() {
  uint32_t now = millis();

  buzzer.update();

  if (now - lastSensorPoll >= SENSOR_POLL_INTERVAL_MS) {
    lastSensorPoll = now;
    pollSensors();
  }

  if (now - lastStatusNotify >= STATUS_NOTIFY_INTERVAL_MS) {
    lastStatusNotify = now;
    ble.notifyStatus(buildStatusLine());
  }
}

