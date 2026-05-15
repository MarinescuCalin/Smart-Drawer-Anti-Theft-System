#include "accel_sensor.h"
#include "pins.h"

static const uint8_t WHO_AM_I_REG = 0x0F;
static const uint8_t CTRL_REG1 = 0x20;
static const uint8_t CTRL_REG4_LIS3DSH = 0x20;
static const uint8_t OUT_X_L = 0x28;

void MotionSensor::begin() {
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(100000);

  scanReport = "I2C";
  detectedAddress = 0;
  detectedWhoAmI = 0;
  detectedType = AccelType::NONE;

  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      scanReport += " 0x";
      if (addr < 16) {
        scanReport += "0";
      }
      scanReport += String(addr, HEX);
      if (detectedAddress == 0 && probeAddress(addr)) {
        detectedAddress = addr;
      }
    }
  }

  if (detectedAddress != 0) {
    configureSensor();
    calibrate();
  }
}

bool MotionSensor::isAvailable() const {
  return detectedAddress != 0 && detectedType != AccelType::NONE;
}

AccelType MotionSensor::type() const {
  return detectedType;
}

String MotionSensor::sensorName() const {
  switch (detectedType) {
    case AccelType::LIS3DSH:
      return "LIS3DSH";
    case AccelType::H3LIS331DL:
      return "H3LIS331DL";
    case AccelType::LIS3DH_COMPATIBLE:
      return "LIS3DH-compatible";
    default:
      return "not-detected";
  }
}

uint8_t MotionSensor::address() const {
  return detectedAddress;
}

uint8_t MotionSensor::whoAmI() const {
  return detectedWhoAmI;
}

void MotionSensor::calibrate() {
  if (!isAvailable()) {
    baselineMagnitude = 0.0f;
    return;
  }

  float sum = 0.0f;
  uint16_t validSamples = 0;
  for (uint16_t i = 0; i < MOTION_CALIBRATION_SAMPLES; i++) {
    int16_t x, y, z;
    if (readRawAxes(x, y, z)) {
      sum += sqrtf((float)x * x + (float)y * y + (float)z * z);
      validSamples++;
    }
    delay(MOTION_SAMPLE_INTERVAL_MS);
  }

  baselineMagnitude = validSamples > 0 ? sum / validSamples : 0.0f;
}

AccelReading MotionSensor::read() {
  AccelReading reading;
  reading.x = 0;
  reading.y = 0;
  reading.z = 0;
  reading.magnitude = 0.0f;
  reading.baselineMagnitude = baselineMagnitude;
  reading.delta = 0.0f;
  reading.motionDetected = false;
  reading.valid = false;

  if (!isAvailable()) {
    return reading;
  }

  if (readRawAxes(reading.x, reading.y, reading.z)) {
    reading.valid = true;
    reading.magnitude = sqrtf((float)reading.x * reading.x +
                              (float)reading.y * reading.y +
                              (float)reading.z * reading.z);
    reading.delta = fabsf(reading.magnitude - baselineMagnitude);
    reading.motionDetected = reading.delta >= MOTION_THRESHOLD_RAW;
  }

  return reading;
}

String MotionSensor::i2cReport() const {
  String report = scanReport;
  if (detectedAddress == 0) {
    report += " accel=none";
    return report;
  }
  report += " accel=";
  report += sensorName();
  report += " addr=0x";
  if (detectedAddress < 16) {
    report += "0";
  }
  report += String(detectedAddress, HEX);
  report += " who=0x";
  if (detectedWhoAmI < 16) {
    report += "0";
  }
  report += String(detectedWhoAmI, HEX);
  return report;
}

bool MotionSensor::probeAddress(uint8_t addr) {
  detectedAddress = addr;
  uint8_t who = 0;
  if (!readRegister(WHO_AM_I_REG, who)) {
    detectedAddress = 0;
    return false;
  }

  AccelType candidate = classify(who);
  if (candidate == AccelType::NONE) {
    detectedAddress = 0;
    return false;
  }

  detectedWhoAmI = who;
  detectedType = candidate;
  return true;
}

bool MotionSensor::readRegister(uint8_t reg, uint8_t &value) const {
  if (detectedAddress == 0) {
    return false;
  }
  Wire.beginTransmission(detectedAddress);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom((int)detectedAddress, 1) != 1) {
    return false;
  }
  value = Wire.read();
  return true;
}

bool MotionSensor::writeRegister(uint8_t reg, uint8_t value) const {
  if (detectedAddress == 0) {
    return false;
  }
  Wire.beginTransmission(detectedAddress);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool MotionSensor::readRawAxes(int16_t &x, int16_t &y, int16_t &z) const {
  if (detectedAddress == 0) {
    return false;
  }

  Wire.beginTransmission(detectedAddress);
  Wire.write(OUT_X_L | 0x80);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom((int)detectedAddress, 6) != 6) {
    return false;
  }

  uint8_t xl = Wire.read();
  uint8_t xh = Wire.read();
  uint8_t yl = Wire.read();
  uint8_t yh = Wire.read();
  uint8_t zl = Wire.read();
  uint8_t zh = Wire.read();

  x = (int16_t)((xh << 8) | xl);
  y = (int16_t)((yh << 8) | yl);
  z = (int16_t)((zh << 8) | zl);
  return true;
}

AccelType MotionSensor::classify(uint8_t who) const {
  if (who == 0x3F) {
    return AccelType::LIS3DSH;
  }
  if (who == 0x32) {
    return AccelType::H3LIS331DL;
  }
  if (who == 0x33) {
    return AccelType::LIS3DH_COMPATIBLE;
  }
  return AccelType::NONE;
}

void MotionSensor::configureSensor() {
  if (!isAvailable()) {
    return;
  }

  if (detectedType == AccelType::LIS3DSH) {
    writeRegister(CTRL_REG4_LIS3DSH, 0x67);
  } else {
    writeRegister(CTRL_REG1, 0x57);
  }
}
