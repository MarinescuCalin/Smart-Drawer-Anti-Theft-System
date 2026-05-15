from __future__ import annotations

import asyncio
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Literal

from .backends import BackendEvent, BleDrawerBackend, MockDrawerBackend

BackendMode = Literal["ble", "mock"]


@dataclass(frozen=True)
class GuiEvent:
    kind: str
    message: str
    payload: object | None = None


class BackendWorker:
    def __init__(self, mode: BackendMode, event_queue: queue.Queue[GuiEvent]) -> None:
        self.mode = mode
        self.event_queue = event_queue
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.backend = self._create_backend(mode)
        self.thread.start()

    def _create_backend(self, mode: BackendMode):
        if mode == "mock":
            return MockDrawerBackend(self._emit_backend_event)
        return BleDrawerBackend(self._emit_backend_event)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _emit_backend_event(self, event: BackendEvent) -> None:
        self.event_queue.put(GuiEvent(event.kind, event.message, event.payload))

    def submit(self, coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(self._guard(coroutine), self.loop)

    async def _guard(self, coroutine):
        try:
            return await coroutine
        except Exception as exc:
            self.event_queue.put(GuiEvent("error", humanize_error(exc)))
            return None

    def scan(self) -> Future:
        return self.submit(self.backend.scan())

    def connect(self, address: str | None = None) -> Future:
        return self.submit(self.backend.connect(address))

    def disconnect(self) -> Future:
        return self.submit(self.backend.disconnect())

    def send_command(self, command: str) -> Future:
        return self.submit(self.backend.send_command(command))

    def shutdown(self) -> None:
        try:
            self.submit(self.backend.disconnect()).result(timeout=2)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)


def humanize_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    if "permission" in lowered or "access" in lowered:
        return f"Bluetooth permission/access problem: {text}"
    if "not found" in lowered:
        return f"ESP32 device not found: {text}"
    if "bleak is not installed" in lowered:
        return text
    if "not connected" in lowered:
        return text
    return f"{exc.__class__.__name__}: {text}"
