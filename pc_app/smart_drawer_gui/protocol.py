from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


STATE_RE = re.compile(r"\b(DISARMED|ARMED|ALARM)\b")
KEY_VALUE_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=([^ ]+)")


@dataclass
class SystemSnapshot:
    state: str = "DISCONNECTED"
    alarm_active: bool = False
    last_event: str = ""
    last_response: str = ""
    connection_state: str = "Disconnected"
    last_update: datetime | None = None
    sensor_values: dict[str, str] = field(default_factory=dict)
    raw_message: str = ""


def validate_pin(pin: str, label: str = "PIN") -> tuple[bool, str]:
    value = pin.strip()
    if not value:
        return False, f"{label} is required."
    if not value.isdigit():
        return False, f"{label} must contain only digits."
    if len(value) < 4 or len(value) > 8:
        return False, f"{label} must be 4-8 digits."
    return True, ""


def build_arm(pin: str) -> str:
    return f"ARM {pin.strip()}"


def build_disarm(pin: str) -> str:
    return f"DISARM {pin.strip()}"


def build_change_pin(old_pin: str, new_pin: str, confirm_pin: str) -> tuple[bool, str]:
    ok, error = validate_pin(old_pin, "Old PIN")
    if not ok:
        return False, error
    ok, error = validate_pin(new_pin, "New PIN")
    if not ok:
        return False, error
    if new_pin.strip() != confirm_pin.strip():
        return False, "New PIN and confirmation do not match."
    return True, f"CHANGE_PIN {old_pin.strip()} {new_pin.strip()}"


def parse_status_message(message: str, current: SystemSnapshot) -> SystemSnapshot:
    snapshot = SystemSnapshot(
        state=current.state,
        alarm_active=current.alarm_active,
        last_event=current.last_event,
        last_response=current.last_response,
        connection_state=current.connection_state,
        last_update=datetime.now(),
        sensor_values=dict(current.sensor_values),
        raw_message=message,
    )

    if message.startswith("STATUS "):
        match = STATE_RE.search(message)
        if match:
            snapshot.state = match.group(1)
            snapshot.alarm_active = snapshot.state == "ALARM"
        snapshot.last_response = message
    elif message.startswith("OK "):
        snapshot.last_response = message
        if "ARMED" in message:
            snapshot.state = "ARMED"
            snapshot.alarm_active = False
        elif "DISARMED" in message:
            snapshot.state = "DISARMED"
            snapshot.alarm_active = False
    elif message.startswith("ALARM "):
        snapshot.state = "ALARM"
        snapshot.alarm_active = True
        snapshot.last_event = message
        snapshot.last_response = message
    elif message.startswith("ERR "):
        snapshot.last_response = message
    elif message:
        snapshot.last_response = message

    for key, value in KEY_VALUE_RE.findall(message):
        snapshot.sensor_values[key] = value

    return snapshot
