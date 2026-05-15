#pragma once

#include <Arduino.h>

static const char *DEVICE_NAME = "SmartDrawerAlarm";

static const char *BLE_SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0";
static const char *BLE_COMMAND_UUID = "12345678-1234-5678-1234-56789abcdef1";
static const char *BLE_STATUS_UUID = "12345678-1234-5678-1234-56789abcdef2";
static const char *BLE_LOG_UUID = "12345678-1234-5678-1234-56789abcdef3";

static const char *DEFAULT_PIN = "1234";

static const uint8_t ACTIVE_LDR_COUNT = 3;
static const uint8_t MAX_LDR_COUNT = 3;
static const uint8_t LIGHT_VOTE_REQUIRED = 2;
static const int LIGHT_THRESHOLD_DELTA = 450;
static const uint8_t LIGHT_AVERAGE_SAMPLES = 16;

static const uint16_t MOTION_CALIBRATION_SAMPLES = 120;
static const uint16_t MOTION_SAMPLE_INTERVAL_MS = 10;
static const float MOTION_THRESHOLD_RAW = 1800.0f;

static const uint32_t SENSOR_POLL_INTERVAL_MS = 80;
static const uint32_t STATUS_NOTIFY_INTERVAL_MS = 1000;
static const uint32_t SERIAL_BAUD_RATE = 115200;

static const uint8_t BUZZER_LEDC_CHANNEL = 0;
static const uint8_t BUZZER_LEDC_RESOLUTION_BITS = 10;
static const uint16_t BUZZER_DUTY = 512;
