from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BleEvent:
    kind: str
    message: str
    timestamp: datetime

    @classmethod
    def now(cls, kind: str, message: str) -> "BleEvent":
        return cls(kind=kind, message=message, timestamp=datetime.now(timezone.utc))

    def as_json_dict(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind,
            "message": self.message,
        }

