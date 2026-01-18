#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# KAGAMI HUB INSTALLATION SCRIPT
# Colony: Forge (e₂) — Deployment infrastructure
#
# This script installs Kagami Hub on a Raspberry Pi or Linux system.
# Run with: sudo ./install.sh
#
# Requirements:
#   - Raspberry Pi OS (Bookworm) or Debian/Ubuntu
#   - Rust toolchain (if building from source)
#   - Network connectivity for model downloads
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Configuration
INSTALL_DIR="${KAGAMI_INSTALL_DIR:-/opt/kagami-hub}"
SERVICE_USER="kagami"
SERVICE_GROUP="kagami"
CONFIG_DIR="${INSTALL_DIR}/config"
MODELS_DIR="${INSTALL_DIR}/models"
LOGS_DIR="${INSTALL_DIR}/logs"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUB_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (sudo ./install.sh)"
        exit 1
    fi
}

detect_platform() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS_NAME="$ID"
        OS_VERSION="$VERSION_CODENAME"
    else
        log_error "Cannot detect OS. /etc/os-release not found."
        exit 1
    fi

    ARCH=$(uname -m)
    if [[ "$ARCH" == "aarch64" ]]; then
        IS_PI=true
        log_info "Detected Raspberry Pi (ARM64)"
    else
        IS_PI=false
        log_info "Detected $ARCH architecture"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════

install_dependencies() {
    log_info "Installing system dependencies..."

    apt-get update

    # Core build dependencies
    apt-get install -y \
        build-essential \
        pkg-config \
        libssl-dev \
        curl \
        wget \
        git

    # Audio dependencies (ALSA)
    apt-get install -y \
        libasound2-dev \
        libasound2 \
        alsa-utils \
        pulseaudio

    # Raspberry Pi specific
    if [[ "$IS_PI" == true ]]; then
        apt-get install -y \
            libraspberrypi-dev \
            raspi-gpio \
            pigpio
    fi

    # Optional: avahi for mDNS
    apt-get install -y avahi-daemon avahi-utils

    log_success "System dependencies installed"
}

# ═══════════════════════════════════════════════════════════════════════════
# USER AND PERMISSIONS
# ═══════════════════════════════════════════════════════════════════════════

create_service_user() {
    log_info "Creating service user: $SERVICE_USER"

    if id "$SERVICE_USER" &>/dev/null; then
        log_info "User $SERVICE_USER already exists"
    else
        useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
        log_success "Created user $SERVICE_USER"
    fi

    # Add to required groups
    for group in audio gpio spi i2c video; do
        if getent group "$group" > /dev/null 2>&1; then
            usermod -a -G "$group" "$SERVICE_USER"
            log_info "Added $SERVICE_USER to group: $group"
        fi
    done
}

setup_gpio_permissions() {
    if [[ "$IS_PI" != true ]]; then
        log_info "Skipping GPIO setup (not Raspberry Pi)"
        return
    fi

    log_info "Configuring GPIO permissions..."

    # Enable SPI
    if ! grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null; then
        echo "dtparam=spi=on" >> /boot/config.txt
        log_warn "SPI enabled in /boot/config.txt - REBOOT REQUIRED"
    fi

    # Enable I2C (for display)
    if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
        echo "dtparam=i2c_arm=on" >> /boot/config.txt
        log_warn "I2C enabled in /boot/config.txt - REBOOT REQUIRED"
    fi

    # Create udev rule for SPI access
    cat > /etc/udev/rules.d/99-kagami-spi.rules << 'EOF'
# Kagami Hub SPI access for LED ring
SUBSYSTEM=="spidev", GROUP="spi", MODE="0660"
EOF

    # Create udev rule for GPIO access
    cat > /etc/udev/rules.d/99-kagami-gpio.rules << 'EOF'
# Kagami Hub GPIO access
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio*", PROGRAM="/bin/sh -c 'chown -R root:gpio /sys/class/gpio && chmod -R 770 /sys/class/gpio'"
EOF

    udevadm control --reload-rules
    udevadm trigger

    log_success "GPIO permissions configured"
}

# ═══════════════════════════════════════════════════════════════════════════
# DIRECTORY STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

create_directories() {
    log_info "Creating directory structure..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$MODELS_DIR"
    mkdir -p "$LOGS_DIR"

    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
    chmod -R 755 "$INSTALL_DIR"
    chmod 770 "$LOGS_DIR"

    log_success "Directories created at $INSTALL_DIR"
}

# ═══════════════════════════════════════════════════════════════════════════
# RUST INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════

install_rust() {
    if command -v cargo &> /dev/null; then
        log_info "Rust already installed: $(rustc --version)"
        return
    fi

    log_info "Installing Rust toolchain..."

    # Install as calling user, not root
    SUDO_USER="${SUDO_USER:-$(whoami)}"
    sudo -u "$SUDO_USER" curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
        sudo -u "$SUDO_USER" sh -s -- -y --default-toolchain stable

    # Source cargo env
    source "$HOME/.cargo/env" 2>/dev/null || true
    source "/home/$SUDO_USER/.cargo/env" 2>/dev/null || true

    log_success "Rust installed"
}

# ═══════════════════════════════════════════════════════════════════════════
# BUILD AND INSTALL BINARY
# ═══════════════════════════════════════════════════════════════════════════

build_hub() {
    log_info "Building Kagami Hub..."

    cd "$HUB_ROOT"

    # Determine features based on platform
    if [[ "$IS_PI" == true ]]; then
        FEATURES="hub-hardware,rpi"
    else
        FEATURES="desktop"
    fi

    log_info "Building with features: $FEATURES"

    # Build release binary
    cargo build --release --features "$FEATURES"

    # Install binary
    cp "target/release/kagami-hub" /usr/local/bin/kagami-hub
    chmod +x /usr/local/bin/kagami-hub

    log_success "Binary installed to /usr/local/bin/kagami-hub"
}

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

install_config() {
    log_info "Installing configuration..."

    # Copy default config if not exists
    if [[ ! -f "$CONFIG_DIR/hub.toml" ]]; then
        cp "$HUB_ROOT/config/hub.toml" "$CONFIG_DIR/hub.toml"
        log_success "Default config installed to $CONFIG_DIR/hub.toml"
    else
        log_info "Config already exists, not overwriting"
    fi

    chown "$SERVICE_USER:$SERVICE_GROUP" "$CONFIG_DIR/hub.toml"
    chmod 640 "$CONFIG_DIR/hub.toml"
}

# ═══════════════════════════════════════════════════════════════════════════
# MODEL DOWNLOADS
# ═══════════════════════════════════════════════════════════════════════════

download_models() {
    log_info "Downloading AI models (this may take a while)..."

    # Whisper base model (150MB)
    WHISPER_MODEL="$MODELS_DIR/whisper-base.bin"
    if [[ ! -f "$WHISPER_MODEL" ]]; then
        log_info "Downloading Whisper base model..."
        wget -q --show-progress -O "$WHISPER_MODEL" \
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
        log_success "Whisper model downloaded"
    else
        log_info "Whisper model already exists"
    fi

    # Piper TTS model (50MB)
    PIPER_MODEL="$MODELS_DIR/en_US-amy-medium.onnx"
    PIPER_CONFIG="$MODELS_DIR/en_US-amy-medium.onnx.json"
    if [[ ! -f "$PIPER_MODEL" ]]; then
        log_info "Downloading Piper TTS model..."
        wget -q --show-progress -O "$PIPER_MODEL" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
        wget -q --show-progress -O "$PIPER_CONFIG" \
            "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
        log_success "Piper TTS model downloaded"
    else
        log_info "Piper model already exists"
    fi

    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$MODELS_DIR"
    chmod -R 644 "$MODELS_DIR"/*

    log_success "Models ready at $MODELS_DIR"
}

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEMD SERVICE
# ═══════════════════════════════════════════════════════════════════════════

install_service() {
    log_info "Installing systemd service..."

    # Copy service file
    SYSTEMD_DIR="$(dirname "$(dirname "$HUB_ROOT")")/deploy/systemd"
    cp "$SYSTEMD_DIR/kagami-hub.service" /etc/systemd/system/kagami-hub.service

    # Reload systemd
    systemctl daemon-reload

    # Enable service (but don't start yet)
    systemctl enable kagami-hub

    log_success "Service installed and enabled"
    log_info "Start with: sudo systemctl start kagami-hub"
}

# ═══════════════════════════════════════════════════════════════════════════
# VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════

verify_installation() {
    log_info "Verifying installation..."

    local ERRORS=0

    # Check binary
    if [[ -x /usr/local/bin/kagami-hub ]]; then
        log_success "Binary: /usr/local/bin/kagami-hub"
    else
        log_error "Binary not found or not executable"
        ((ERRORS++))
    fi

    # Check config
    if [[ -f "$CONFIG_DIR/hub.toml" ]]; then
        log_success "Config: $CONFIG_DIR/hub.toml"
    else
        log_error "Config not found"
        ((ERRORS++))
    fi

    # Check models
    if [[ -f "$MODELS_DIR/whisper-base.bin" ]]; then
        log_success "Whisper model: present"
    else
        log_warn "Whisper model: missing (voice commands will fail)"
    fi

    if [[ -f "$MODELS_DIR/en_US-amy-medium.onnx" ]]; then
        log_success "Piper model: present"
    else
        log_warn "Piper model: missing (TTS will fail)"
    fi

    # Check service
    if systemctl is-enabled kagami-hub &>/dev/null; then
        log_success "Service: enabled"
    else
        log_warn "Service: not enabled"
    fi

    # Check audio
    if aplay -l &>/dev/null; then
        log_success "Audio: ALSA devices available"
    else
        log_warn "Audio: No ALSA devices found"
    fi

    # Check GPIO (Pi only)
    if [[ "$IS_PI" == true ]]; then
        if [[ -c /dev/spidev0.0 ]]; then
            log_success "SPI: /dev/spidev0.0 available"
        else
            log_warn "SPI: device not available (LED ring will not work)"
        fi
    fi

    if [[ $ERRORS -gt 0 ]]; then
        log_error "Installation verification failed with $ERRORS errors"
        return 1
    else
        log_success "Installation verified successfully!"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

main() {
    echo "═══════════════════════════════════════════════════════════════════"
    echo "        KAGAMI HUB INSTALLER"
    echo "        Colony: Forge (e₂) — Building the voice of your home"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""

    check_root
    detect_platform

    echo ""
    log_info "Installation directory: $INSTALL_DIR"
    log_info "Platform: $OS_NAME $OS_VERSION ($ARCH)"
    echo ""

    # Run installation steps
    install_dependencies
    create_service_user
    setup_gpio_permissions
    create_directories
    install_config
    download_models
    build_hub
    install_service

    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    verify_installation
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""

    if [[ "$IS_PI" == true ]]; then
        log_warn "IMPORTANT: Reboot required to enable SPI/I2C for GPIO access"
        log_info "After reboot, start the hub with: sudo systemctl start kagami-hub"
    else
        log_info "Start the hub with: sudo systemctl start kagami-hub"
    fi

    log_info "Check status: sudo systemctl status kagami-hub"
    log_info "View logs: journalctl -u kagami-hub -f"
    log_info "Configuration: $CONFIG_DIR/hub.toml"

    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "        Installation complete!"
    echo "        鏡 — The Hub is ready to listen."
    echo "═══════════════════════════════════════════════════════════════════"
}

main "$@"
