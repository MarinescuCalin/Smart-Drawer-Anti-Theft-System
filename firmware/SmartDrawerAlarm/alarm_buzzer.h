#pragma once

#include <Arduino.h>

class BuzzerController {
public:
  void begin();
  void setAlarmActive(bool active);
  void update();
  void stop();

private:
  bool alarmActive = false;
  uint8_t step = 0;
  uint32_t stepStartedAt = 0;

  void toneOn(uint16_t frequency);
  void toneOff();
  void advanceStep();
};

