#include "ble_service.h"
#include "config.h"

BleCommandCallbacks::BleCommandCallbacks(BleCommandService *service) : owner(service) {}

void BleCommandCallbacks::onWrite(NimBLECharacteristic *characteristic, NimBLEConnInfo &connInfo) {
  (void)connInfo;
  std::string value = characteristic->getValue();
  owner->handleWrite(String(value.c_str()));
}

BleServerCallbacks::BleServerCallbacks(BleCommandService *service) : owner(service) {}

void BleServerCallbacks::onConnect(NimBLEServer *server, NimBLEConnInfo &connInfo) {
  (void)server;
  (void)connInfo;
  owner->handleConnect();
}

void BleServerCallbacks::onDisconnect(NimBLEServer *server, NimBLEConnInfo &connInfo, int reason) {
  (void)server;
  (void)connInfo;
  (void)reason;
  owner->handleDisconnect();
}

void BleCommandService::begin(CommandHandler handler) {
  commandHandler = handler;

  NimBLEDevice::init(DEVICE_NAME);
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);

  server = NimBLEDevice::createServer();
  server->setCallbacks(new BleServerCallbacks(this));

  NimBLEService *service = server->createService(BLE_SERVICE_UUID);

  commandCharacteristic = service->createCharacteristic(
      BLE_COMMAND_UUID,
      NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
  commandCharacteristic->setCallbacks(new BleCommandCallbacks(this));

  statusCharacteristic = service->createCharacteristic(
      BLE_STATUS_UUID,
      NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
  statusCharacteristic->setValue("STATUS DISARMED");

  logCharacteristic = service->createCharacteristic(
      BLE_LOG_UUID,
      NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
  logCharacteristic->setValue("BOOT");

  NimBLEAdvertising *advertising = NimBLEDevice::getAdvertising();
  advertising->addServiceUUID(BLE_SERVICE_UUID);
  advertising->enableScanResponse(true);
  advertising->start();
}

void BleCommandService::notifyStatus(const String &status) {
  if (statusCharacteristic == nullptr) {
    return;
  }
  statusCharacteristic->setValue(status.c_str());
  if (clientConnected) {
    statusCharacteristic->notify();
  }
}

void BleCommandService::notifyLog(const String &entry) {
  if (logCharacteristic == nullptr) {
    return;
  }
  logCharacteristic->setValue(entry.c_str());
  if (clientConnected) {
    logCharacteristic->notify();
  }
}

bool BleCommandService::connected() const {
  return clientConnected;
}

void BleCommandService::handleWrite(const String &payload) {
  if (commandHandler) {
    commandHandler(payload);
  }
}

void BleCommandService::handleConnect() {
  clientConnected = true;
}

void BleCommandService::handleDisconnect() {
  clientConnected = false;
  NimBLEDevice::startAdvertising();
}
