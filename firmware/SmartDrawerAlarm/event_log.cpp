#include "event_log.h"

void EventLogger::begin() {
  nextIndex = 0;
  count = 0;
  add("BOOT");
}

void EventLogger::add(const String &message) {
  String entry = String(millis()) + " " + message;
  entries[nextIndex] = entry;
  nextIndex = (nextIndex + 1) % CAPACITY;
  if (count < CAPACITY) {
    count++;
  }
  Serial.println("[LOG] " + entry);
}

String EventLogger::latest() const {
  if (count == 0) {
    return "";
  }
  uint8_t index = (nextIndex + CAPACITY - 1) % CAPACITY;
  return entries[index];
}

String EventLogger::dump() const {
  String output;
  for (uint8_t i = 0; i < count; i++) {
    uint8_t index = (nextIndex + CAPACITY - count + i) % CAPACITY;
    output += entries[index];
    if (i + 1 < count) {
      output += "\n";
    }
  }
  return output;
}

