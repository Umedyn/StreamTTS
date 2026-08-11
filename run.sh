#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

find_python() {
    for cand in python3.13 python3.12 python3.11 python3; do
        if command -v "$cand" >/dev/null 2>&1; then
            ver=$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)
            [ "${ver%%.*}" -eq 3 ] && [ "${ver##*.}" -ge 11 ] && { echo "$cand"; return 0; }
        fi
    done
    return 1
}

PY=$(find_python) || {
    echo "[setup] Python 3.11+ not found. Install it:"
    case "$(uname -s)" in
        Darwin) echo "  brew install python@3.12" ;;
        Linux)  echo "  Debian/Ubuntu: sudo apt install python3 python3-venv libportaudio2"
                echo "  Fedora:        sudo dnf install python3 portaudio"
                echo "  Arch:          sudo pacman -S python portaudio" ;;
    esac
    exit 1
}

if [ ! -x ".venv/bin/python" ]; then
    echo "[setup] Creating virtual environment with $PY ..."
    "$PY" -m venv .venv
    ./.venv/bin/python -m pip install --upgrade pip
    echo "[setup] Installing dependencies..."
    ./.venv/bin/pip install -r requirements.txt
fi

exec ./.venv/bin/python src/main.py "$@"