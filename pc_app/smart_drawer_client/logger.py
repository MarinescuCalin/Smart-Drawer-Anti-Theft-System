import json
from pathlib import Path

from .models import BleEvent


class JsonlEventLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: BleEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.as_json_dict(), ensure_ascii=False) + "\n")

