#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"

find_python() {
    local candidate

    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
                printf '%s\n' "$candidate"
                return 0
            fi
        fi
    done

    return 1
}

PYTHON_BIN="$(find_python || true)"

if [[ -z "$PYTHON_BIN" ]]; then
    echo "[ERROR] Python 3.8+ was not found."
    echo "Install Python first, for example: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

echo "[INFO] Python: $("$PYTHON_BIN" --version)"
echo "[INFO] Creating virtual environment: $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

echo "[INFO] Installing Python dependencies"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

cat <<'MSG'

[OK] Ubuntu environment is ready.

Start the app with:
  ./start_latex_cleaner.sh

Clipboard support:
  Wayland: sudo apt install wl-clipboard
  X11:     sudo apt install xclip xsel
MSG
