VALID_COMMANDS = {
    "ARM",
    "DISARM",
    "STATUS",
    "CHANGE_PIN",
    "GET_LOG",
    "CALIBRATE_LIGHT",
    "CALIBRATE_MOTION",
    "PING",
    "HELP",
    "QUIT",
    "EXIT",
}


def normalize_command(raw: str) -> str:
    command = " ".join(raw.strip().split())
    if not command:
        return ""
    verb, *rest = command.split(" ")
    return " ".join([verb.upper(), *rest]).strip()


def validate_command(command: str) -> tuple[bool, str]:
    if not command:
        return False, "Empty command."
    verb = command.split(" ", 1)[0].upper()
    if verb not in VALID_COMMANDS:
        return False, f"Unknown command: {verb}"
    if verb in {"ARM", "DISARM"} and len(command.split()) != 2:
        return False, f"Usage: {verb} <PIN>"
    if verb == "CHANGE_PIN" and len(command.split()) != 3:
        return False, "Usage: CHANGE_PIN <old_pin> <new_pin>"
    return True, ""


HELP_TEXT = """Commands:
  ARM <PIN>
  DISARM <PIN>
  STATUS
  CHANGE_PIN <old_pin> <new_pin>
  CALIBRATE_LIGHT
  CALIBRATE_MOTION
  GET_LOG
  PING
  HELP
  QUIT
"""

