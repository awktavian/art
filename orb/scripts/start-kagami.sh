#!/usr/bin/env bash
#
# 鏡 Kagami API Starter Script
# Cross-platform launcher for macOS, Linux, and WSL
#
# Usage:
#   ./scripts/start-kagami.sh [options]
#
# Options:
#   --local       Enable local mode (skip Redis/etcd)
#   --production  Enable production mode (requires all services)
#   --port PORT   Specify port (default: 8001)
#   --install     Install as system service
#   --uninstall   Remove system service
#   --status      Check service status
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KAGAMI_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
PORT="${KAGAMI_PORT:-8001}"
LOG_LEVEL="${KAGAMI_LOG_LEVEL:-INFO}"
LOCAL_MODE="${KAGAMI_LOCAL_MODE:-1}"

# Detect platform
detect_platform() {
    case "$(uname -s)" in
        Darwin*)
            echo "macos"
            ;;
        Linux*)
            if grep -q Microsoft /proc/version 2>/dev/null; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        CYGWIN*|MINGW*|MSYS*)
            echo "windows"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

PLATFORM=$(detect_platform)

# Find Python
find_python() {
    local python_cmd=""

    # Check for pyenv
    if command -v pyenv &>/dev/null; then
        python_cmd="$(pyenv which python 2>/dev/null || true)"
    fi

    # Check for venv
    if [[ -z "$python_cmd" && -x "$KAGAMI_ROOT/.venv/bin/python" ]]; then
        python_cmd="$KAGAMI_ROOT/.venv/bin/python"
    fi

    # Fall back to system python
    if [[ -z "$python_cmd" ]]; then
        python_cmd="$(command -v python3 || command -v python)"
    fi

    echo "$python_cmd"
}

PYTHON=$(find_python)

# Setup PYTHONPATH
# NOTE: Only add /packages dir, NOT individual packages, to avoid shadowing
# Python's built-in 'types' module with kagami_smarthome/types.py
setup_pythonpath() {
    export PYTHONPATH="${KAGAMI_ROOT}:${KAGAMI_ROOT}/packages${PYTHONPATH:+:$PYTHONPATH}"
}

# Install service based on platform
install_service() {
    case "$PLATFORM" in
        macos)
            echo "📦 Installing launchd service..."
            local plist="$HOME/Library/LaunchAgents/com.kagami.api.plist"
            cp "$KAGAMI_ROOT/deploy/launchd/com.kagami.api.plist" "$plist" 2>/dev/null || \
            cp "$HOME/Library/LaunchAgents/com.kagami.api.plist" "$plist" 2>/dev/null
            launchctl load "$plist"
            echo "✅ Installed: launchctl load $plist"
            ;;
        linux|wsl)
            echo "📦 Installing systemd service..."
            sudo cp "$KAGAMI_ROOT/deploy/kagami-api.service" /etc/systemd/system/
            sudo systemctl daemon-reload
            sudo systemctl enable kagami-api
            echo "✅ Installed: systemctl enable kagami-api"
            ;;
        windows)
            echo "📦 Windows service installation..."
            echo "Run as Administrator:"
            echo "  sc create KagamiAPI binPath=\"$PYTHON $KAGAMI_ROOT/scripts/kagami_api_launcher.py\" start=auto"
            ;;
        *)
            echo "❌ Unsupported platform: $PLATFORM"
            exit 1
            ;;
    esac
}

# Uninstall service
uninstall_service() {
    case "$PLATFORM" in
        macos)
            echo "🗑️ Removing launchd service..."
            local plist="$HOME/Library/LaunchAgents/com.kagami.api.plist"
            launchctl unload "$plist" 2>/dev/null || true
            rm -f "$plist"
            echo "✅ Removed"
            ;;
        linux|wsl)
            echo "🗑️ Removing systemd service..."
            sudo systemctl stop kagami-api 2>/dev/null || true
            sudo systemctl disable kagami-api 2>/dev/null || true
            sudo rm -f /etc/systemd/system/kagami-api.service
            sudo systemctl daemon-reload
            echo "✅ Removed"
            ;;
        windows)
            echo "🗑️ Run as Administrator:"
            echo "  sc stop KagamiAPI"
            echo "  sc delete KagamiAPI"
            ;;
        *)
            echo "❌ Unsupported platform: $PLATFORM"
            exit 1
            ;;
    esac
}

# Check service status
check_status() {
    case "$PLATFORM" in
        macos)
            launchctl list | grep -q "com.kagami.api" && echo "🟢 Running" || echo "🔴 Stopped"
            ;;
        linux|wsl)
            systemctl is-active kagami-api &>/dev/null && echo "🟢 Running" || echo "🔴 Stopped"
            ;;
        windows)
            sc query KagamiAPI 2>/dev/null | grep -q "RUNNING" && echo "🟢 Running" || echo "🔴 Stopped"
            ;;
        *)
            curl -s "http://127.0.0.1:$PORT/health" &>/dev/null && echo "🟢 Running" || echo "🔴 Stopped"
            ;;
    esac
}

# Start directly (foreground)
start_direct() {
    setup_pythonpath

    echo "🪞 Kagami API starting..."
    echo "   Platform: $PLATFORM"
    echo "   Python: $PYTHON"
    echo "   Port: $PORT"
    echo "   Local Mode: $LOCAL_MODE"
    echo ""

    cd "$KAGAMI_ROOT"

    if [[ "$LOCAL_MODE" == "1" ]]; then
        export KAGAMI_LOCAL_MODE=1
        export KAGAMI_SKIP_DISTRIBUTED=1
    fi

    exec "$PYTHON" "$KAGAMI_ROOT/scripts/kagami_api_launcher.py" \
        --port "$PORT" \
        --log-level "$LOG_LEVEL"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --local)
            LOCAL_MODE="1"
            shift
            ;;
        --production)
            LOCAL_MODE="0"
            export KAGAMI_FULL_OPERATION=1
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --install)
            install_service
            exit 0
            ;;
        --uninstall)
            uninstall_service
            exit 0
            ;;
        --status)
            check_status
            exit 0
            ;;
        --help|-h)
            head -30 "$0" | tail -20
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Default action: start
start_direct
