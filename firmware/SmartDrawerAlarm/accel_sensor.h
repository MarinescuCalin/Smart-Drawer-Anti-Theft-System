#pragma once

#include <Arduino.h>
#include <Wire.h>
#include "config.h"

enum class AccelType {
  NONE,
  LIS3DSH,
  H3LIS331DL,
  LIS3DH_COMPATIBLE
};

struct AccelReading {
  int16_t x;
  int16_t y;
  int16_t z;
  float magnitude;
  float baselineMagnitude;
  float delta;
  bool motionDetected;
  bool valid;
};

class MotionSensor {
public:
  void begin();
  bool isAvailable() const;
  AccelType type() const;
  String sensorName() const;
  uint8_t address() const;
  uint8_t whoAmI() const;
  void calibrate();
  AccelReading read();
  String i2cReport() const;

private:
  uint8_t detectedAddress = 0;
  uint8_t detectedWhoAmI = 0;
  AccelType detectedType = AccelType::NONE;
  float baselineMagnitude = 0.0f;
  String scanReport;

  bool probeAddress(uint8_t addr);
  bool readRegister(uint8_t reg, uint8_t &value) const;
  bool writeRegister(uint8_t reg, uint8_t value) const;
  bool readRawAxes(int16_t &x, int16_t &y, int16_t &z) const;
  AccelType classify(uint8_t who) const;
  void configureSensor();
};
