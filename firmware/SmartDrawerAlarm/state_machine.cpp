#include "state_machine.h"

SystemState SecurityStateMachine::state() const {
  return currentState;
}

AlarmReason SecurityStateMachine::reason() const {
  return currentReason;
}

bool SecurityStateMachine::isArmed() const {
  return currentState == SystemState::ARMED;
}

bool SecurityStateMachine::isAlarm() const {
  return currentState == SystemState::ALARM;
}

bool SecurityStateMachine::arm() {
  if (currentState == SystemState::ARMED) {
    return false;
  }
  currentState = SystemState::ARMED;
  currentReason = AlarmReason::NONE;
  return true;
}

bool SecurityStateMachine::disarm() {
  if (currentState == SystemState::DISARMED) {
    return false;
  }
  currentState = SystemState::DISARMED;
  currentReason = AlarmReason::NONE;
  return true;
}

bool SecurityStateMachine::trigger(bool light, bool motion) {
  if (currentState != SystemState::ARMED || (!light && !motion)) {
    return false;
  }

  currentState = SystemState::ALARM;
  if (light && motion) {
    currentReason = AlarmReason::LIGHT_AND_MOTION;
  } else if (light) {
    currentReason = AlarmReason::LIGHT;
  } else {
    currentReason = AlarmReason::MOTION;
  }
  return true;
}

String SecurityStateMachine::stateText() const {
  switch (currentState) {
    case SystemState::DISARMED:
      return "DISARMED";
    case SystemState::ARMED:
      return "ARMED";
    case SystemState::ALARM:
      return "ALARM";
  }
  return "UNKNOWN";
}

String SecurityStateMachine::reasonText() const {
  switch (currentReason) {
    case AlarmReason::LIGHT:
      return "LIGHT";
    case AlarmReason::MOTION:
      return "MOTION";
    case AlarmReason::LIGHT_AND_MOTION:
      return "LIGHT_AND_MOTION";
    default:
      return "NONE";
  }
}

