import asyncio
from collections.abc import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from . import config
from .models import BleEvent

EventCallback = Callable[[BleEvent], None]


class SmartDrawerBleClient:
    def __init__(self, on_event: EventCallback) -> None:
        self.on_event = on_event
        self.device: BLEDevice | None = None
        self.client: BleakClient | None = None
        self.last_status: str | None = None
        self._status_event = asyncio.Event()

    async def scan(self, timeout: float = config.SCAN_TIMEOUT_SECONDS) -> BLEDevice:
        self.on_event(BleEvent.now("scan", f"Scanning for {config.DEVICE_NAME}..."))
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

        for device, advertisement in devices.values():
            names = {device.name, advertisement.local_name}
            service_uuids = {uuid.lower() for uuid in advertisement.service_uuids}
            if config.DEVICE_NAME in names or config.SERVICE_UUID.lower() in service_uuids:
                self.device = device
                self.on_event(BleEvent.now("scan", f"Found {device.address} ({device.name})"))
                return device

        raise RuntimeError(f"BLE device {config.DEVICE_NAME} was not found.")

    async def connect(self) -> None:
        if self.device is None:
            await self.scan()

        assert self.device is not None
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
        self.on_event(BleEvent.now("connect", "Connected and notifications enabled."))

    async def disconnect(self) -> None:
        if self.client is not None and self.client.is_connected:
            await self.client.disconnect()
        self.on_event(BleEvent.now("disconnect", "Disconnected."))

    async def ensure_connected(self) -> None:
        if self.client is not None and self.client.is_connected:
            return
        for attempt in range(1, 4):
            try:
                self.on_event(BleEvent.now("reconnect", f"Reconnect attempt {attempt}/3"))
                await self.connect()
                return
            except Exception as exc:
                self.on_event(BleEvent.now("error", f"Reconnect failed: {exc}"))
                await asyncio.sleep(config.RECONNECT_DELAY_SECONDS)
        raise RuntimeError("Unable to reconnect to SmartDrawerAlarm.")

    async def send_command(self, command: str) -> str | None:
        await self.ensure_connected()
        assert self.client is not None

        self._status_event.clear()
        await self.client.write_gatt_char(config.COMMAND_UUID, command.encode("utf-8"), response=True)
        self.on_event(BleEvent.now("command", command))

        try:
            await asyncio.wait_for(
                self._status_event.wait(),
                timeout=config.COMMAND_RESPONSE_TIMEOUT_SECONDS,
            )
            return self.last_status
        except TimeoutError:
            self.on_event(BleEvent.now("warning", "No status notification received before timeout."))
            return None

    def _on_status(self, _: int, data: bytearray) -> None:
        message = data.decode("utf-8", errors="replace").strip()
        self.last_status = message
        self._status_event.set()
        self.on_event(BleEvent.now("status", message))

    def _on_log(self, _: int, data: bytearray) -> None:
        message = data.decode("utf-8", errors="replace").strip()
        self.on_event(BleEvent.now("device_log", message))

    def _on_disconnect(self, _: BleakClient) -> None:
        self.on_event(BleEvent.now("disconnect", "Device disconnected."))

