#pragma once

#include <Arduino.h>
#include "config.h"
#include "pins.h"

struct LdrReading {
  int raw[MAX_LDR_COUNT];
  int baseline[MAX_LDR_COUNT];
  bool detected[MAX_LDR_COUNT];
  uint8_t activeCount;
  uint8_t voteCount;
  bool lightDetected;
};

class LdrSensorArray {
public:
  void begin();
  void calibrate();
  LdrReading read();
  String summary() const;

private:
  const uint8_t pins[MAX_LDR_COUNT] = {LDR1_PIN, LDR2_PIN, LDR3_PIN};
  int baseline[MAX_LDR_COUNT] = {0, 0, 0};

  int readAveraged(uint8_t pin) const;
};
