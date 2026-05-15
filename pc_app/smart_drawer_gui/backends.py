from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Protocol

from smart_drawer_client import config


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    address: str
    details: str = ""

    @property
    def label(self) -> str:
        suffix = f" - {self.details}" if self.details else ""
        return f"{self.name or 'Unknown'} ({self.address}){suffix}"


@dataclass(frozen=True)
class BackendEvent:
    kind: str
    message: str
    payload: object | None = None
    timestamp: datetime = field(default_factory=datetime.now)


EventSink = Callable[[BackendEvent], None]


class DrawerBackend(Protocol):
    async def scan(self) -> list[DeviceInfo]: ...
    async def connect(self, address: str | None = None) -> None: ...
    async def disconnect(self) -> None: ...
    async def send_command(self, command: str) -> str | None: ...
    def is_connected(self) -> bool: ...


class BleDrawerBackend:
    def __init__(self, emit: EventSink) -> None:
        self.emit = emit
        self.client = None
        self.device = None
        self.last_status: str | None = None
        self._status_event: asyncio.Event | None = None

    async def scan(self) -> list[DeviceInfo]:
        try:
            from bleak import BleakScanner
        except Exception as exc:  # pragma: no cover - depends on host setup
            raise RuntimeError("Bleak is not installed. Run: pip install -r requirements.txt") from exc

        self.emit(BackendEvent("connection", "Scanning for BLE devices..."))
        found = await BleakScanner.discover(timeout=config.SCAN_TIMEOUT_SECONDS, return_adv=True)
        devices: list[DeviceInfo] = []
        preferred: object | None = None

        for device, advertisement in found.values():
            name = device.name or advertisement.local_name or "Unknown"
            service_uuids = {uuid.lower() for uuid in advertisement.service_uuids}
            details = "SmartDrawerAlarm" if (
                name == config.DEVICE_NAME or config.SERVICE_UUID.lower() in service_uuids
            ) else ""
            item = DeviceInfo(name=name, address=device.address, details=details)
            devices.append(item)
            if details and preferred is None:
                preferred = device

        devices.sort(key=lambda item: (item.details != "SmartDrawerAlarm", item.name, item.address))
        self.emit(BackendEvent("devices", f"Found {len(devices)} BLE device(s).", devices))
        if preferred is not None:
            self.device = preferred
        return devices

    async def connect(self, address: str | None = None) -> None:
        try:
            from bleak import BleakClient, BleakScanner
        except Exception as exc:  # pragma: no cover - depends on host setup
            raise RuntimeError("Bleak is not installed. Run: pip install -r requirements.txt") from exc

        self._status_event = asyncio.Event()
        self.emit(BackendEvent("connection", "Connecting..."))

        target = address.strip() if address else None
        if target:
            self.device = target
        elif self.device is None:
            device = await BleakScanner.find_device_by_filter(
                lambda d, ad: d.name == config.DEVICE_NAME
                or ad.local_name == config.DEVICE_NAME
                or config.SERVICE_UUID.lower() in {uuid.lower() for uuid in ad.service_uuids},
                timeout=config.SCAN_TIMEOUT_SECONDS,
            )
            if device is None:
                raise RuntimeError(f"{config.DEVICE_NAME} was not found.")
            self.device = device

        self.client = BleakClient(
            self.device,
            timeout=config.CONNECT_TIMEOUT_SECONDS,
            disconnected_callback=self._on_disconnect,
        )
        await self.client.connect()
        if not self.client.is_connected:
            raise RuntimeError("BLE connection failed.")

        await self.client.start_notify(config.STATUS_UUID, self._on_status)
        await self.client.start_notify(config.LOG_UUID, self._on_log)
        self.emit(BackendEvent("connection", "Connected."))

    async def disconnect(self) -> None:
        if self.client is not None and self.client.is_connected:
            await self.client.disconnect()
        self.emit(BackendEvent("connection", "Disconnected."))

    async def send_command(self, command: str) -> str | None:
        if self.client is None or not self.client.is_connected:
            raise RuntimeError("Not connected to ESP32.")
        assert self._status_event is not None

        self._status_event.clear()
        await self.client.write_gatt_char(config.COMMAND_UUID, command.encode("utf-8"), response=True)
        self.emit(BackendEvent("command", command))

        try:
            await asyncio.wait_for(self._status_event.wait(), timeout=config.COMMAND_RESPONSE_TIMEOUT_SECONDS)
            return self.last_status
        except TimeoutError:
            self.emit(BackendEvent("warning", "Command sent, but no status notification arrived before timeout."))
            return None

    def is_connected(self) -> bool:
        return bool(self.client is not None and self.client.is_connected)

    def _on_status(self, _: int, data: bytearray) -> None:
        message = data.decode("utf-8", errors="replace").strip()
        self.last_status = message
        if self._status_event is not None:
            self._status_event.set()
        self.emit(BackendEvent("status", message))

    def _on_log(self, _: int, data: bytearray) -> None:
        message = data.decode("utf-8", errors="replace").strip()
        self.emit(BackendEvent("device_log", message))

    def _on_disconnect(self, _: object) -> None:
        self.emit(BackendEvent("connection", "Device disconnected."))


class MockDrawerBackend:
    def __init__(self, emit: EventSink) -> None:
        self.emit = emit
        self.connected = False
        self.state = "DISARMED"
        self.pin = "1234"
        self.event_counter = 0

    async def scan(self) -> list[DeviceInfo]:
        await asyncio.sleep(0.4)
        devices = [DeviceInfo(name=config.DEVICE_NAME, address="MOCK-ESP32", details="Mock device")]
        self.emit(BackendEvent("devices", "Mock scan complete.", devices))
        return devices

    async def connect(self, address: str | None = None) -> None:
        await asyncio.sleep(0.3)
        self.connected = True
        self.emit(BackendEvent("connection", "Connected to mock ESP32."))
        await self._publish_status()

    async def disconnect(self) -> None:
        await asyncio.sleep(0.1)
        self.connected = False
        self.emit(BackendEvent("connection", "Disconnected from mock ESP32."))

    async def send_command(self, command: str) -> str | None:
        if not self.connected:
            raise RuntimeError("Mock backend is not connected.")
        await asyncio.sleep(0.2)
        self.emit(BackendEvent("command", command))
        response = self._handle_command(command)
        self.emit(BackendEvent("status", response))
        if response.startswith("ALARM "):
            self.emit(BackendEvent("device_log", f"{self.event_counter} {response}"))
        return response

    def is_connected(self) -> bool:
        return self.connected

    def _handle_command(self, command: str) -> str:
        parts = command.strip().split()
        verb = parts[0].upper() if parts else ""
        if verb == "PING":
            return "PONG"
        if verb == "STATUS":
            return self._status_line()
        if verb == "CALIBRATE_LIGHT":
            return "OK CALIBRATED_LIGHT LDR raw1=920 base1=918 raw2=934 base2=931 raw3=901 base3=900 deltaThreshold=450"
        if verb == "CALIBRATE_MOTION":
            return "OK CALIBRATED_MOTION I2C 0x19 accel=LIS3DH-compatible addr=0x19 who=0x33"
        if verb == "GET_LOG":
            return "0 BOOT\n1 MOCK READY"
        if verb == "ARM":
            if len(parts) != 2 or parts[1] != self.pin:
                return "ERR WRONG_PIN"
            self.state = "ARMED"
            return "OK ARMED"
        if verb == "DISARM":
            if len(parts) != 2 or parts[1] != self.pin:
                return "ERR WRONG_PIN"
            self.state = "DISARMED"
            return "OK DISARMED"
        if verb == "CHANGE_PIN":
            if len(parts) != 3 or parts[1] != self.pin:
                return "ERR WRONG_PIN"
            self.pin = parts[2]
            return "OK PIN_CHANGED"
        if verb == "MOCK_ALARM":
            self.state = "ALARM"
            self.event_counter += 1
            return "ALARM LIGHT lightVotes=2 motionDelta=0.0"
        return "ERR INVALID_COMMAND"

    async def _publish_status(self) -> None:
        self.emit(BackendEvent("status", self._status_line()))

    def _status_line(self) -> str:
        return (
            f"STATUS {self.state} reason=NONE ble=connected accel=LIS3DH-compatible who=0x33 "
            "LDR raw1=920 base1=918 raw2=934 base2=931 raw3=901 base3=900 deltaThreshold=450"
        )
