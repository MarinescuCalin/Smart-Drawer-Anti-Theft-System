import argparse
import asyncio
import sys
from pathlib import Path

from . import config
from .ble_client import SmartDrawerBleClient
from .commands import HELP_TEXT, normalize_command, validate_command
from .logger import JsonlEventLogger
from .models import BleEvent


class ConsoleApp:
    def __init__(self, log_path=None) -> None:
        self.logger = JsonlEventLogger(log_path or config.DEFAULT_LOG_FILE)
        self.client = SmartDrawerBleClient(self.handle_event)

    def handle_event(self, event: BleEvent) -> None:
        self.logger.write(event)
        print(f"[{event.kind}] {event.message}")

    async def run_once(self, command: str) -> int:
        await self.client.connect()
        try:
            response = await self.client.send_command(command)
            if response:
                print(response)
            return 0
        finally:
            await self.client.disconnect()

    async def interactive(self) -> int:
        print("Smart Drawer BLE Client")
        print(HELP_TEXT)
        await self.client.connect()

        try:
            while True:
                raw = await asyncio.to_thread(input, "smart-drawer> ")
                command = normalize_command(raw)
                if not command:
                    continue
                verb = command.split(" ", 1)[0].upper()
                if verb in {"QUIT", "EXIT"}:
                    return 0
                if verb == "HELP":
                    print(HELP_TEXT)
                    continue

                ok, error = validate_command(command)
                if not ok:
                    print(error)
                    continue

                response = await self.client.send_command(command)
                if response:
                    print(response)
        finally:
            await self.client.disconnect()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Drawer Anti-Theft BLE client")
    parser.add_argument(
        "--command",
        "-c",
        help="Send one command, for example: 'STATUS' or 'ARM 1234'.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=str(config.DEFAULT_LOG_FILE),
        help="Path for local JSONL BLE/application logs.",
    )
    return parser.parse_args(argv)


async def async_main(argv: list[str]) -> int:
    args = parse_args(argv)
    app = ConsoleApp(log_path=Path(args.log_file))

    if args.command:
        command = normalize_command(args.command)
        ok, error = validate_command(command)
        if not ok:
            print(error, file=sys.stderr)
            return 2
        return await app.run_once(command)

    return await app.interactive()


def main() -> None:
    try:
        raise SystemExit(asyncio.run(async_main(sys.argv[1:])))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
