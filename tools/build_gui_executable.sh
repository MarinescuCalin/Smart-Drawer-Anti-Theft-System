#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/pc_app/.venv/bin/python"
APP_ENTRY="$PROJECT_ROOT/pc_app/run_gui.py"
ICON_PNG="$PROJECT_ROOT/assets/icons/smart_drawer_icon_filled_512.png"
APP_NAME="SmartDrawerGUI"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing virtual environment. Create it with:"
  echo "  cd \"$PROJECT_ROOT/pc_app\""
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "$ICON_PNG" ]]; then
  echo "Missing icon: $ICON_PNG"
  exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pyinstaller

cd "$PROJECT_ROOT"
"$VENV_PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PNG" \
  --paths "$PROJECT_ROOT/pc_app" \
  --collect-submodules bleak \
  "$APP_ENTRY"

echo "Executable created at:"
echo "  $PROJECT_ROOT/dist/$APP_NAME/$APP_NAME"
