#pragma once

#include <Arduino.h>

class EventLogger {
public:
  static const uint8_t CAPACITY = 24;

  void begin();
  void add(const String &message);
  String latest() const;
  String dump() const;

private:
  String entries[CAPACITY];
  uint8_t nextIndex = 0;
  uint8_t count = 0;
};

