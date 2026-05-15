#include "alarm_buzzer.h"
#include "config.h"
#include "pins.h"

#if ESP_ARDUINO_VERSION_MAJOR >= 3
static bool ledcAttached = false;
#endif

void BuzzerController::begin() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttached = ledcAttach(BUZZER_PIN, 1000, BUZZER_LEDC_RESOLUTION_BITS);
#else
  ledcSetup(BUZZER_LEDC_CHANNEL, 1000, BUZZER_LEDC_RESOLUTION_BITS);
  ledcAttachPin(BUZZER_PIN, BUZZER_LEDC_CHANNEL);
#endif
  stop();
}

void BuzzerController::setAlarmActive(bool active) {
  if (alarmActive == active) {
    return;
  }
  alarmActive = active;
  step = 0;
  stepStartedAt = millis();
  if (alarmActive) {
    toneOn(1000);
  } else {
    toneOff();
  }
}

void BuzzerController::update() {
  if (!alarmActive) {
    return;
  }
  advanceStep();
}

void BuzzerController::stop() {
  alarmActive = false;
  step = 0;
  toneOff();
}

void BuzzerController::toneOn(uint16_t frequency) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  if (ledcAttached) {
    ledcWriteTone(BUZZER_PIN, frequency);
    ledcWrite(BUZZER_PIN, BUZZER_DUTY);
  }
#else
  ledcWriteTone(BUZZER_LEDC_CHANNEL, frequency);
  ledcWrite(BUZZER_LEDC_CHANNEL, BUZZER_DUTY);
#endif
}

void BuzzerController::toneOff() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  if (ledcAttached) {
    ledcWrite(BUZZER_PIN, 0);
  }
#else
  ledcWrite(BUZZER_LEDC_CHANNEL, 0);
#endif
}

void BuzzerController::advanceStep() {
  const uint16_t durations[] = {200, 100, 200, 300};
  uint32_t now = millis();
  if (now - stepStartedAt < durations[step]) {
    return;
  }

  step = (step + 1) % 4;
  stepStartedAt = now;
  if (step == 0) {
    toneOn(1000);
  } else if (step == 1 || step == 3) {
    toneOff();
  } else if (step == 2) {
    toneOn(1500);
  }
}

