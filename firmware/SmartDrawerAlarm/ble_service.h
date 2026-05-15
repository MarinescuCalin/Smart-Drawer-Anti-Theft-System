#pragma once

#include <Arduino.h>
#include <functional>
#include <NimBLEDevice.h>

typedef std::function<void(const String &)> CommandHandler;

class BleCommandService;

class BleCommandCallbacks : public NimBLECharacteristicCallbacks {
public:
  explicit BleCommandCallbacks(BleCommandService *service);
  void onWrite(NimBLECharacteristic *characteristic, NimBLEConnInfo &connInfo) override;

private:
  BleCommandService *owner;
};

class BleServerCallbacks : public NimBLEServerCallbacks {
public:
  explicit BleServerCallbacks(BleCommandService *service);
  void onConnect(NimBLEServer *server, NimBLEConnInfo &connInfo) override;
  void onDisconnect(NimBLEServer *server, NimBLEConnInfo &connInfo, int reason) override;

private:
  BleCommandService *owner;
};

class BleCommandService {
public:
  void begin(CommandHandler handler);
  void notifyStatus(const String &status);
  void notifyLog(const String &entry);
  bool connected() const;
  void handleWrite(const String &payload);
  void handleConnect();
  void handleDisconnect();

private:
  NimBLEServer *server = nullptr;
  NimBLECharacteristic *commandCharacteristic = nullptr;
  NimBLECharacteristic *statusCharacteristic = nullptr;
  NimBLECharacteristic *logCharacteristic = nullptr;
  CommandHandler commandHandler;
  bool clientConnected = false;
};
