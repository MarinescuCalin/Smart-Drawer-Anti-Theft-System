#pragma once

#include <Arduino.h>

enum class SystemState {
  DISARMED,
  ARMED,
  ALARM
};

enum class AlarmReason {
  NONE,
  LIGHT,
  MOTION,
  LIGHT_AND_MOTION
};

class SecurityStateMachine {
public:
  SystemState state() const;
  AlarmReason reason() const;
  bool isArmed() const;
  bool isAlarm() const;
  bool arm();
  bool disarm();
  bool trigger(bool light, bool motion);
  String stateText() const;
  String reasonText() const;

private:
  SystemState currentState = SystemState::DISARMED;
  AlarmReason currentReason = AlarmReason::NONE;
};

