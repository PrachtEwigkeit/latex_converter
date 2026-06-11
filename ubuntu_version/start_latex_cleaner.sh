#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="$APP_DIR/app.py"
BASE_PORT="${LATEX_CLEANER_PORT:-8501}"
DRY_RUN=0
INSTALL_DEPS=0
OPEN_BROWSER=1

usage() {
    cat <<'MSG'
Usage: ./start_latex_cleaner.sh [options]

Options:
  --dry-run       Check Python, dependencies, and port without starting Streamlit.
  --install       Create/update .venv and install requirements before starting.
  --no-browser    Do not open the browser automatically.
  --port PORT     Start searching for a free port from PORT.
  -h, --help      Show this help.
MSG
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --install)
            INSTALL_DEPS=1
            shift
            ;;
        --no-browser)
            OPEN_BROWSER=0
            shift
            ;;
        --port)
            if [[ $# -lt 2 ]]; then
                echo "[ERROR] --port requires a value."
                exit 1
            fi
            BASE_PORT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

find_python() {
    local candidate

    if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
        printf '%s\n' "$APP_DIR/.venv/bin/python"
        return 0
    fi

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

if [[ "$INSTALL_DEPS" -eq 1 ]]; then
    "$APP_DIR/install_ubuntu.sh"
    PYTHON_BIN="$APP_DIR/.venv/bin/python"
fi

if [[ ! -f "$APP_FILE" ]]; then
    echo "[ERROR] app.py was not found in: $APP_DIR"
    exit 1
fi

if ! "$PYTHON_BIN" -c 'import streamlit' >/dev/null 2>&1; then
    echo "[ERROR] Streamlit is not installed for: $PYTHON_BIN"
    echo
    echo "Run one of these commands first:"
    echo "  ./install_ubuntu.sh"
    echo "  ./start_latex_cleaner.sh --install"
    exit 1
fi

PORT="$BASE_PORT"
PORT_ATTEMPTS=0
MAX_PORT_ATTEMPTS=100

while ! "$PYTHON_BIN" -c 'import socket, sys
port = int(sys.argv[1])
sock = socket.socket()
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
' "$PORT" >/dev/null 2>&1; do
    PORT=$((PORT + 1))
    PORT_ATTEMPTS=$((PORT_ATTEMPTS + 1))

    if [[ "$PORT_ATTEMPTS" -ge "$MAX_PORT_ATTEMPTS" ]]; then
        echo "[ERROR] Could not find a free local port from $BASE_PORT to $((PORT - 1))."
        echo "If you are running inside a restricted sandbox, local port binding may be blocked."
        echo "Otherwise, try another start port: ./start_latex_cleaner.sh --port 8600"
        exit 1
    fi
done

echo "Python: $PYTHON_BIN"
echo "Local URL: http://localhost:$PORT"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run OK. No server was started."
    exit 0
fi

if [[ "$OPEN_BROWSER" -eq 1 ]] && command -v xdg-open >/dev/null 2>&1; then
    (
        sleep 2
        xdg-open "http://localhost:$PORT" >/dev/null 2>&1 || true
    ) &
fi

echo "Starting ChatGPT LaTeX Cleaner. Press Ctrl+C to stop."
"$PYTHON_BIN" -m streamlit run "$APP_FILE" --server.port "$PORT" --server.headless true
