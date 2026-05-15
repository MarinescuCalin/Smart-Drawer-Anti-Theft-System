#include "ldr_sensor.h"
#include "pins.h"

void LdrSensorArray::begin() {
  analogReadResolution(12);
  for (uint8_t i = 0; i < MAX_LDR_COUNT; i++) {
    pinMode(pins[i], INPUT);
  }
  calibrate();
}

void LdrSensorArray::calibrate() {
  for (uint8_t i = 0; i < ACTIVE_LDR_COUNT; i++) {
    baseline[i] = readAveraged(pins[i]);
  }
}

LdrReading LdrSensorArray::read() {
  LdrReading reading;
  reading.activeCount = ACTIVE_LDR_COUNT;
  reading.voteCount = 0;
  reading.lightDetected = false;

  for (uint8_t i = 0; i < MAX_LDR_COUNT; i++) {
    reading.raw[i] = 0;
    reading.baseline[i] = baseline[i];
    reading.detected[i] = false;
  }

  for (uint8_t i = 0; i < ACTIVE_LDR_COUNT; i++) {
    reading.raw[i] = readAveraged(pins[i]);
    int delta = abs(reading.raw[i] - baseline[i]);
    reading.detected[i] = delta >= LIGHT_THRESHOLD_DELTA;
    if (reading.detected[i]) {
      reading.voteCount++;
    }
  }

  reading.lightDetected = reading.voteCount >= LIGHT_VOTE_REQUIRED;
  return reading;
}

String LdrSensorArray::summary() const {
  String text = "LDR";
  for (uint8_t i = 0; i < ACTIVE_LDR_COUNT; i++) {
    text += " raw";
    text += i + 1;
    text += "=";
    text += analogRead(pins[i]);
    text += " base";
    text += i + 1;
    text += "=";
    text += baseline[i];
  }
  text += " deltaThreshold=";
  text += LIGHT_THRESHOLD_DELTA;
  return text;
}

int LdrSensorArray::readAveraged(uint8_t pin) const {
  uint32_t sum = 0;
  for (uint8_t i = 0; i < LIGHT_AVERAGE_SAMPLES; i++) {
    sum += analogRead(pin);
    delay(1);
  }
  return sum / LIGHT_AVERAGE_SAMPLES;
}

