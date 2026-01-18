#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# KAGAMI HUB — ONE-LINE INSTALLER
# Colony: Forge (e₂) — Bulletproof deployment
#
# Usage: curl -sSL https://kagami.run/install | bash
#
# This installer:
#   - Detects everything automatically (Pi model, RAM, audio, GPIO)
#   - Fixes everything automatically (I2C, SPI, permissions)
#   - Downloads pre-compiled binaries (no build required)
#   - Configures interactively with sane defaults
#   - Verifies everything works
#   - Is idempotent (safe to run multiple times)
#
# Supported: Raspberry Pi 3/4/5, Debian/Ubuntu ARM64
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

readonly VERSION="1.0.0"
readonly RELEASE_URL="https://github.com/kagami/kagami-hub/releases/latest/download"
readonly MODELS_CDN="https://huggingface.co"
readonly INSTALL_DIR="/opt/kagami-hub"
readonly CONFIG_DIR="${INSTALL_DIR}/config"
readonly MODELS_DIR="${INSTALL_DIR}/models"
readonly LOGS_DIR="${INSTALL_DIR}/logs"
readonly SERVICE_USER="kagami"
readonly SERVICE_GROUP="kagami"

# Model URLs
readonly WHISPER_TINY_URL="${MODELS_CDN}/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
readonly WHISPER_BASE_URL="${MODELS_CDN}/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
readonly PIPER_MODEL_URL="${MODELS_CDN}/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
readonly PIPER_CONFIG_URL="${MODELS_CDN}/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"

# ═══════════════════════════════════════════════════════════════════════════════
# COLORS AND OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

# Check if stdout is a terminal
if [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly BLUE='\033[0;34m'
    readonly MAGENTA='\033[0;35m'
    readonly CYAN='\033[0;36m'
    readonly WHITE='\033[1;37m'
    readonly BOLD='\033[1m'
    readonly DIM='\033[2m'
    readonly NC='\033[0m'
else
    readonly RED='' GREEN='' YELLOW='' BLUE='' MAGENTA='' CYAN='' WHITE='' BOLD='' DIM='' NC=''
fi

# Spinner characters
readonly SPINNER="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

print_banner() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}${BOLD}"
    echo "     鏡  KAGAMI HUB INSTALLER"
    echo "         Voice-First Smart Home Assistant"
    echo -e "${NC}${DIM}         Version ${VERSION}${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

log_step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}${BOLD}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

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

log_detail() {
    echo -e "${DIM}       $1${NC}"
}

# Progress bar for downloads
show_progress() {
    local current=$1
    local total=$2
    local width=40
    local percentage=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))

    printf "\r${BLUE}["
    printf "%${filled}s" | tr ' ' '='
    printf "%${empty}s" | tr ' ' ' '
    printf "]${NC} %3d%%" $percentage
}

# Spinner for long operations
spinner_start() {
    local msg="$1"
    local i=0
    while true; do
        printf "\r${BLUE}%s${NC} %s" "${SPINNER:i++%${#SPINNER}:1}" "$msg"
        sleep 0.1
    done &
    SPINNER_PID=$!
    disown
}

spinner_stop() {
    if [[ -n "${SPINNER_PID:-}" ]]; then
        kill "$SPINNER_PID" 2>/dev/null || true
        wait "$SPINNER_PID" 2>/dev/null || true
        printf "\r%*s\r" 60 ""
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

# Global detection results
declare PI_MODEL=""
declare PI_REVISION=""
declare RAM_MB=0
declare IS_PI=false
declare ARCH=""
declare OS_NAME=""
declare OS_VERSION=""
declare AUDIO_DEVICES=""
declare I2C_ENABLED=false
declare SPI_ENABLED=false
declare GPIO_ACCESSIBLE=false
declare NEEDS_REBOOT=false
declare EXISTING_INSTALL=false
declare EXISTING_VERSION=""

detect_system() {
    log_step "DETECTING SYSTEM"

    # Architecture
    ARCH=$(uname -m)
    log_info "Architecture: ${WHITE}${ARCH}${NC}"

    # OS
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS_NAME="$ID"
        OS_VERSION="${VERSION_CODENAME:-unknown}"
        log_info "Operating System: ${WHITE}${PRETTY_NAME:-$OS_NAME}${NC}"
    else
        log_error "Cannot detect OS. /etc/os-release not found."
        exit 1
    fi

    # Raspberry Pi detection
    if [[ -f /proc/device-tree/model ]]; then
        local model_string
        model_string=$(tr -d '\0' < /proc/device-tree/model)

        if [[ "$model_string" == *"Raspberry Pi"* ]]; then
            IS_PI=true

            # Extract Pi model number
            if [[ "$model_string" == *"Pi 5"* ]]; then
                PI_MODEL="5"
            elif [[ "$model_string" == *"Pi 4"* ]]; then
                PI_MODEL="4"
            elif [[ "$model_string" == *"Pi 3"* ]]; then
                PI_MODEL="3"
            elif [[ "$model_string" == *"Pi Zero 2"* ]]; then
                PI_MODEL="Zero2"
            elif [[ "$model_string" == *"Pi Zero"* ]]; then
                PI_MODEL="Zero"
            else
                PI_MODEL="Unknown"
            fi

            log_success "Raspberry Pi ${WHITE}${PI_MODEL}${NC} detected"
            log_detail "$model_string"
        fi
    fi

    # Revision (for exact model identification)
    if [[ -f /proc/cpuinfo ]]; then
        PI_REVISION=$(grep "^Revision" /proc/cpuinfo | awk '{print $3}' || echo "unknown")
        log_detail "Revision: $PI_REVISION"
    fi

    # RAM detection
    RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
    log_info "RAM: ${WHITE}${RAM_MB} MB${NC}"

    if [[ $RAM_MB -lt 512 ]]; then
        log_warn "Low RAM detected. Kagami Hub requires at least 512MB."
        log_warn "Performance may be degraded."
    elif [[ $RAM_MB -lt 1024 ]]; then
        log_info "Using Whisper tiny model (optimized for low RAM)"
    else
        log_info "Using Whisper base model (better accuracy)"
    fi

    # Audio detection
    detect_audio

    # GPIO detection (Pi only)
    if [[ "$IS_PI" == true ]]; then
        detect_gpio
    fi

    # Check for existing installation
    detect_existing_install
}

detect_audio() {
    log_info "Detecting audio devices..."

    # ALSA devices
    if command -v arecord &>/dev/null; then
        local capture_devices
        capture_devices=$(arecord -l 2>/dev/null || echo "")

        if [[ -n "$capture_devices" ]] && [[ "$capture_devices" != *"no soundcards found"* ]]; then
            local device_count
            device_count=$(echo "$capture_devices" | grep -c "^card" || echo "0")
            log_success "Found ${WHITE}${device_count}${NC} audio input device(s)"

            while IFS= read -r line; do
                if [[ "$line" == card* ]]; then
                    log_detail "$line"
                fi
            done <<< "$capture_devices"
            AUDIO_DEVICES="$capture_devices"
        else
            log_warn "No audio input devices found"
            log_detail "You'll need a USB microphone for voice commands"
        fi
    else
        log_warn "ALSA utilities not installed"
    fi

    # Playback devices
    if command -v aplay &>/dev/null; then
        local playback_devices
        playback_devices=$(aplay -l 2>/dev/null || echo "")

        if [[ -n "$playback_devices" ]] && [[ "$playback_devices" != *"no soundcards found"* ]]; then
            local device_count
            device_count=$(echo "$playback_devices" | grep -c "^card" || echo "0")
            log_success "Found ${WHITE}${device_count}${NC} audio output device(s)"
        else
            log_warn "No audio output devices found"
        fi
    fi
}

detect_gpio() {
    log_info "Checking GPIO status..."

    # Check I2C
    if [[ -e /dev/i2c-1 ]] || [[ -e /dev/i2c-0 ]]; then
        I2C_ENABLED=true
        log_success "I2C is ${WHITE}enabled${NC}"
    else
        I2C_ENABLED=false
        log_warn "I2C is disabled (will enable automatically)"
    fi

    # Check SPI
    if [[ -e /dev/spidev0.0 ]] || [[ -e /dev/spidev0.1 ]]; then
        SPI_ENABLED=true
        log_success "SPI is ${WHITE}enabled${NC}"
    else
        SPI_ENABLED=false
        log_warn "SPI is disabled (required for LED ring, will enable)"
    fi

    # Check GPIO access
    if [[ -e /dev/gpiomem ]]; then
        GPIO_ACCESSIBLE=true
        log_success "GPIO memory access available"
    else
        GPIO_ACCESSIBLE=false
        log_warn "GPIO memory not accessible"
    fi
}

detect_existing_install() {
    if [[ -d "$INSTALL_DIR" ]] || [[ -f /usr/local/bin/kagami-hub ]]; then
        EXISTING_INSTALL=true

        if [[ -x /usr/local/bin/kagami-hub ]]; then
            EXISTING_VERSION=$(/usr/local/bin/kagami-hub --version 2>/dev/null | head -1 || echo "unknown")
        fi

        log_info "Existing installation detected"
        if [[ -n "$EXISTING_VERSION" ]]; then
            log_detail "Current version: $EXISTING_VERSION"
        fi
    else
        EXISTING_INSTALL=false
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# PREREQUISITES CHECK
# ═══════════════════════════════════════════════════════════════════════════════

check_prerequisites() {
    log_step "CHECKING PREREQUISITES"

    local errors=0

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This installer must be run as root"
        echo ""
        echo -e "  Run with: ${WHITE}sudo bash -c \"\$(curl -sSL https://kagami.run/install)\"${NC}"
        echo ""
        exit 1
    fi
    log_success "Running as root"

    # Check architecture
    if [[ "$ARCH" != "aarch64" ]] && [[ "$ARCH" != "armv7l" ]]; then
        log_warn "Unsupported architecture: $ARCH"
        log_warn "Kagami Hub is designed for Raspberry Pi (ARM)"
        log_warn "Installation will continue but may not work correctly"
    fi

    # Check for required commands
    local required_cmds=("curl" "wget" "systemctl")
    for cmd in "${required_cmds[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Required command not found: $cmd"
            ((errors++))
        fi
    done

    # Check internet connectivity
    log_info "Checking internet connectivity..."
    if curl -sSf --connect-timeout 5 "https://github.com" > /dev/null 2>&1; then
        log_success "Internet connection OK"
    else
        log_error "Cannot reach GitHub. Check your internet connection."
        ((errors++))
    fi

    # Check disk space
    local available_space
    available_space=$(df -m / | awk 'NR==2 {print $4}')
    if [[ $available_space -lt 500 ]]; then
        log_error "Insufficient disk space. Need at least 500MB, have ${available_space}MB"
        ((errors++))
    else
        log_success "Disk space OK (${available_space}MB available)"
    fi

    if [[ $errors -gt 0 ]]; then
        log_error "Prerequisites check failed with $errors error(s)"
        exit 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM FIXES (AUTO-CONFIGURATION)
# ═══════════════════════════════════════════════════════════════════════════════

fix_system() {
    log_step "CONFIGURING SYSTEM"

    # Install dependencies
    install_dependencies

    # Create service user
    create_service_user

    # Fix GPIO permissions (Pi only)
    if [[ "$IS_PI" == true ]]; then
        fix_gpio
    fi

    # Create directory structure
    create_directories
}

install_dependencies() {
    log_info "Installing system dependencies..."

    # Suppress apt output unless there's an error
    local apt_log
    apt_log=$(mktemp)

    if ! apt-get update > "$apt_log" 2>&1; then
        log_error "Failed to update package lists"
        cat "$apt_log"
        rm -f "$apt_log"
        exit 1
    fi

    local packages=(
        "libasound2"
        "libasound2-dev"
        "alsa-utils"
        "libssl1.1 || libssl3"
        "avahi-daemon"
        "avahi-utils"
        "curl"
        "wget"
    )

    # Raspberry Pi specific
    if [[ "$IS_PI" == true ]]; then
        packages+=("pigpio" "raspi-gpio" "python3-rpi.gpio")
    fi

    local installed=0
    local failed=0

    for pkg in "${packages[@]}"; do
        # Handle OR packages (pkg1 || pkg2)
        if [[ "$pkg" == *"||"* ]]; then
            local pkg1 pkg2
            pkg1=$(echo "$pkg" | awk -F'||' '{print $1}' | xargs)
            pkg2=$(echo "$pkg" | awk -F'||' '{print $2}' | xargs)

            if dpkg -l "$pkg1" 2>/dev/null | grep -q "^ii"; then
                log_detail "Package $pkg1 already installed"
                ((installed++))
            elif dpkg -l "$pkg2" 2>/dev/null | grep -q "^ii"; then
                log_detail "Package $pkg2 already installed"
                ((installed++))
            elif apt-get install -y "$pkg1" >> "$apt_log" 2>&1; then
                log_detail "Installed $pkg1"
                ((installed++))
            elif apt-get install -y "$pkg2" >> "$apt_log" 2>&1; then
                log_detail "Installed $pkg2"
                ((installed++))
            else
                log_warn "Could not install $pkg1 or $pkg2"
            fi
        else
            if dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
                log_detail "Package $pkg already installed"
            elif apt-get install -y "$pkg" >> "$apt_log" 2>&1; then
                log_detail "Installed $pkg"
                ((installed++))
            else
                log_warn "Could not install $pkg"
                ((failed++))
            fi
        fi
    done

    rm -f "$apt_log"

    if [[ $failed -eq 0 ]]; then
        log_success "Dependencies installed"
    else
        log_warn "$failed package(s) failed to install"
    fi
}

create_service_user() {
    log_info "Setting up service user..."

    if id "$SERVICE_USER" &>/dev/null; then
        log_detail "User '$SERVICE_USER' already exists"
    else
        useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
        log_success "Created user '$SERVICE_USER'"
    fi

    # Add to required groups
    local groups=("audio" "gpio" "spi" "i2c" "video" "dialout")
    for group in "${groups[@]}"; do
        if getent group "$group" > /dev/null 2>&1; then
            usermod -a -G "$group" "$SERVICE_USER" 2>/dev/null || true
            log_detail "Added to group: $group"
        fi
    done

    log_success "User configured"
}

fix_gpio() {
    log_info "Configuring GPIO/SPI/I2C..."

    # Determine boot config location (Pi 5 uses different path)
    local boot_config=""
    if [[ -f /boot/firmware/config.txt ]]; then
        boot_config="/boot/firmware/config.txt"
    elif [[ -f /boot/config.txt ]]; then
        boot_config="/boot/config.txt"
    else
        log_warn "Cannot find boot config file"
        return
    fi

    local config_changed=false

    # Enable SPI
    if ! grep -q "^dtparam=spi=on" "$boot_config" 2>/dev/null; then
        echo "dtparam=spi=on" >> "$boot_config"
        log_info "Enabled SPI in boot config"
        config_changed=true
    else
        log_detail "SPI already enabled"
    fi

    # Enable I2C
    if ! grep -q "^dtparam=i2c_arm=on" "$boot_config" 2>/dev/null; then
        echo "dtparam=i2c_arm=on" >> "$boot_config"
        log_info "Enabled I2C in boot config"
        config_changed=true
    else
        log_detail "I2C already enabled"
    fi

    # Enable audio
    if ! grep -q "^dtparam=audio=on" "$boot_config" 2>/dev/null; then
        echo "dtparam=audio=on" >> "$boot_config"
        log_info "Enabled audio in boot config"
        config_changed=true
    fi

    # Create udev rules for SPI access
    cat > /etc/udev/rules.d/99-kagami-spi.rules << 'EOF'
# Kagami Hub SPI access for LED ring
SUBSYSTEM=="spidev", GROUP="spi", MODE="0660"
EOF

    # Create udev rules for GPIO access
    cat > /etc/udev/rules.d/99-kagami-gpio.rules << 'EOF'
# Kagami Hub GPIO access
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio*", PROGRAM="/bin/sh -c 'chown -R root:gpio /sys/class/gpio && chmod -R 770 /sys/class/gpio'"
EOF

    # Reload udev rules
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true

    if [[ "$config_changed" == true ]]; then
        NEEDS_REBOOT=true
        log_warn "Boot config changed - reboot required"
    fi

    log_success "GPIO/SPI/I2C configured"
}

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

# ═══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD AND INSTALL
# ═══════════════════════════════════════════════════════════════════════════════

download_and_install() {
    log_step "DOWNLOADING KAGAMI HUB"

    # Download binary
    download_binary

    # Download models
    download_models

    # Install default config
    install_default_config

    # Install systemd service
    install_systemd_service
}

download_binary() {
    log_info "Downloading Kagami Hub binary..."

    local binary_url=""
    local binary_name=""

    # Determine correct binary for architecture
    if [[ "$ARCH" == "aarch64" ]]; then
        binary_name="kagami-hub-linux-arm64"
    elif [[ "$ARCH" == "armv7l" ]]; then
        binary_name="kagami-hub-linux-armv7"
    else
        binary_name="kagami-hub-linux-arm64"  # Default
    fi

    binary_url="${RELEASE_URL}/${binary_name}"

    local tmp_binary
    tmp_binary=$(mktemp)

    # Download with progress
    log_detail "URL: $binary_url"

    if curl -fSL --progress-bar -o "$tmp_binary" "$binary_url" 2>&1; then
        # Make executable and install
        chmod +x "$tmp_binary"
        mv "$tmp_binary" /usr/local/bin/kagami-hub
        log_success "Binary installed to /usr/local/bin/kagami-hub"
    else
        # If release binary not available, show build instructions
        rm -f "$tmp_binary"
        log_warn "Pre-built binary not available"
        log_info "Building from source instead..."
        build_from_source
    fi
}

build_from_source() {
    log_info "Building from source (this may take 10-20 minutes on Pi)..."

    # Check if Rust is installed
    if ! command -v cargo &>/dev/null; then
        log_info "Installing Rust toolchain..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi

    # Clone repository
    local tmp_dir
    tmp_dir=$(mktemp -d)
    cd "$tmp_dir"

    log_info "Cloning repository..."
    git clone --depth 1 https://github.com/kagami/kagami-hub.git
    cd kagami-hub/apps/hub/kagami-hub

    # Build with appropriate features
    local features=""
    if [[ "$IS_PI" == true ]]; then
        features="hub-hardware,rpi"
    else
        features="desktop"
    fi

    log_info "Building with features: $features"
    cargo build --release --features "$features"

    # Install binary
    cp target/release/kagami-hub /usr/local/bin/kagami-hub
    chmod +x /usr/local/bin/kagami-hub

    # Cleanup
    cd /
    rm -rf "$tmp_dir"

    log_success "Binary built and installed"
}

download_models() {
    log_info "Downloading AI models..."

    # Select Whisper model based on RAM
    local whisper_url=""
    local whisper_file=""

    if [[ $RAM_MB -lt 1024 ]]; then
        whisper_url="$WHISPER_TINY_URL"
        whisper_file="whisper-tiny.bin"
        log_detail "Using Whisper tiny model (low RAM system)"
    else
        whisper_url="$WHISPER_BASE_URL"
        whisper_file="whisper-base.bin"
        log_detail "Using Whisper base model"
    fi

    # Download Whisper model
    local whisper_path="${MODELS_DIR}/${whisper_file}"
    if [[ ! -f "$whisper_path" ]]; then
        log_info "Downloading Whisper model (~75-150MB)..."
        if wget -q --show-progress -O "$whisper_path" "$whisper_url"; then
            log_success "Whisper model downloaded"
        else
            log_error "Failed to download Whisper model"
            log_detail "You can manually download from: $whisper_url"
        fi
    else
        log_detail "Whisper model already exists"
    fi

    # Download Piper TTS model
    local piper_model="${MODELS_DIR}/en_US-amy-medium.onnx"
    local piper_config="${MODELS_DIR}/en_US-amy-medium.onnx.json"

    if [[ ! -f "$piper_model" ]]; then
        log_info "Downloading Piper TTS model (~50MB)..."
        wget -q --show-progress -O "$piper_model" "$PIPER_MODEL_URL" || log_warn "Failed to download Piper model"
        wget -q --show-progress -O "$piper_config" "$PIPER_CONFIG_URL" || log_warn "Failed to download Piper config"

        if [[ -f "$piper_model" ]]; then
            log_success "Piper TTS model downloaded"
        fi
    else
        log_detail "Piper model already exists"
    fi

    # Set permissions
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$MODELS_DIR"
    chmod -R 644 "$MODELS_DIR"/* 2>/dev/null || true

    log_success "Models ready"
}

install_default_config() {
    local config_file="${CONFIG_DIR}/hub.toml"

    if [[ -f "$config_file" ]]; then
        log_detail "Config file exists, preserving"
        return
    fi

    log_info "Creating default configuration..."

    # Determine Whisper model file
    local whisper_model="base"
    if [[ $RAM_MB -lt 1024 ]]; then
        whisper_model="tiny"
    fi

    cat > "$config_file" << EOF
# Kagami Hub Configuration
# Generated by installer v${VERSION}

[general]
name = "Kagami Hub"
location = "Living Room"
api_url = "http://kagami.local:8001"

[wake_word]
engine = "porcupine"
sensitivity = 0.5
phrase = "Hey Kagami"

[audio]
input_device = "default"
output_device = "default"
sample_rate = 16000
channels = 1

[stt]
engine = "whisper"
model = "${whisper_model}"
language = "en"

[tts]
use_api = true
colony = "kagami"
volume = 0.8

[led_ring]
enabled = true
count = 7
pin = 18
brightness = 0.5

[display]
type = "none"
width = 128
height = 64

[commands]
movie = "execute_scene movie_mode"
goodnight = "execute_scene goodnight"
welcome = "execute_scene welcome_home"

# h(x) >= 0. Always.
EOF

    chown "$SERVICE_USER:$SERVICE_GROUP" "$config_file"
    chmod 640 "$config_file"

    log_success "Default config created"
}

install_systemd_service() {
    log_info "Installing systemd service..."

    cat > /etc/systemd/system/kagami-hub.service << 'EOF'
[Unit]
Description=Kagami Hub - Voice-First Smart Home Assistant
Documentation=https://github.com/kagami/kagami-hub
After=network-online.target sound.target
Wants=network-online.target
Requires=sound.target

[Service]
Type=simple
User=kagami
Group=kagami
WorkingDirectory=/opt/kagami-hub

Environment="RUST_LOG=info"
Environment="KAGAMI_HUB_CONFIG=/opt/kagami-hub/config/hub.toml"
Environment="ALSA_CARD=default"

ExecStart=/usr/local/bin/kagami-hub
ExecReload=/bin/kill -HUP $MAINPID

Restart=on-failure
RestartSec=10s
TimeoutStartSec=30s
TimeoutStopSec=30s

LimitNOFILE=65536
LimitMEMLOCK=infinity

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=false
PrivateDevices=false

SupplementaryGroups=audio gpio spi i2c video

ReadWritePaths=/opt/kagami-hub/config
ReadWritePaths=/opt/kagami-hub/logs
ReadWritePaths=/tmp

DeviceAllow=/dev/spidev* rw
DeviceAllow=/dev/snd/* rw
DeviceAllow=/dev/gpiomem rw

StandardOutput=journal
StandardError=journal
SyslogIdentifier=kagami-hub

CapabilityBoundingSet=CAP_SYS_RAWIO CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_SYS_RAWIO

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable kagami-hub

    log_success "Systemd service installed and enabled"
}

# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

configure_interactive() {
    log_step "CONFIGURATION"

    local config_file="${CONFIG_DIR}/hub.toml"

    echo ""
    echo -e "${WHITE}Let's configure your Kagami Hub.${NC}"
    echo -e "${DIM}Press Enter to accept defaults shown in [brackets].${NC}"
    echo ""

    # API URL
    local current_api_url
    current_api_url=$(grep "^api_url" "$config_file" 2>/dev/null | cut -d'"' -f2 || echo "http://kagami.local:8001")

    read -r -p "$(echo -e "${CYAN}Kagami API URL${NC} [$current_api_url]: ")" api_url
    api_url="${api_url:-$current_api_url}"

    # Wake word sensitivity
    local current_sensitivity
    current_sensitivity=$(grep "^sensitivity" "$config_file" 2>/dev/null | awk '{print $3}' || echo "0.5")

    echo ""
    echo -e "${DIM}Wake word sensitivity (0.0-1.0): lower = fewer false triggers, higher = more responsive${NC}"
    read -r -p "$(echo -e "${CYAN}Wake word sensitivity${NC} [$current_sensitivity]: ")" sensitivity
    sensitivity="${sensitivity:-$current_sensitivity}"

    # LED count
    local current_led_count
    current_led_count=$(grep "^count" "$config_file" 2>/dev/null | awk '{print $3}' || echo "7")

    echo ""
    read -r -p "$(echo -e "${CYAN}LED ring count${NC} [$current_led_count]: ")" led_count
    led_count="${led_count:-$current_led_count}"

    # Location
    local current_location
    current_location=$(grep "^location" "$config_file" 2>/dev/null | cut -d'"' -f2 || echo "Living Room")

    echo ""
    read -r -p "$(echo -e "${CYAN}Hub location${NC} [$current_location]: ")" location
    location="${location:-$current_location}"

    # Update config file
    log_info "Updating configuration..."

    # Use sed to update values
    sed -i "s|^api_url = .*|api_url = \"$api_url\"|" "$config_file"
    sed -i "s|^sensitivity = .*|sensitivity = $sensitivity|" "$config_file"
    sed -i "s|^count = .*|count = $led_count|" "$config_file"
    sed -i "s|^location = .*|location = \"$location\"|" "$config_file"

    log_success "Configuration updated"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

verify_installation() {
    log_step "VERIFYING INSTALLATION"

    local errors=0
    local warnings=0

    # Check binary
    if [[ -x /usr/local/bin/kagami-hub ]]; then
        log_success "Binary: /usr/local/bin/kagami-hub"
    else
        log_error "Binary not found or not executable"
        ((errors++))
    fi

    # Check config
    if [[ -f "${CONFIG_DIR}/hub.toml" ]]; then
        log_success "Config: ${CONFIG_DIR}/hub.toml"
    else
        log_error "Config not found"
        ((errors++))
    fi

    # Check models
    if [[ -f "${MODELS_DIR}/whisper-tiny.bin" ]] || [[ -f "${MODELS_DIR}/whisper-base.bin" ]]; then
        log_success "Whisper model: present"
    else
        log_warn "Whisper model: missing (voice commands will fail)"
        ((warnings++))
    fi

    if [[ -f "${MODELS_DIR}/en_US-amy-medium.onnx" ]]; then
        log_success "Piper TTS model: present"
    else
        log_warn "Piper TTS model: missing (local TTS will fail)"
        ((warnings++))
    fi

    # Check service
    if systemctl is-enabled kagami-hub &>/dev/null; then
        log_success "Service: enabled"
    else
        log_warn "Service: not enabled"
        ((warnings++))
    fi

    # Test audio input
    log_info "Testing audio input..."
    if arecord -l 2>/dev/null | grep -q "^card"; then
        log_success "Audio input: devices available"

        # Quick recording test
        if timeout 1 arecord -q -f cd -d 1 /dev/null 2>/dev/null; then
            log_success "Audio input: recording works"
        else
            log_warn "Audio input: recording may have issues"
            ((warnings++))
        fi
    else
        log_warn "Audio input: no devices found"
        log_detail "Connect a USB microphone for voice commands"
        ((warnings++))
    fi

    # Test audio output
    log_info "Testing audio output..."
    if aplay -l 2>/dev/null | grep -q "^card"; then
        log_success "Audio output: devices available"
    else
        log_warn "Audio output: no devices found"
        ((warnings++))
    fi

    # Test GPIO (Pi only)
    if [[ "$IS_PI" == true ]]; then
        log_info "Testing GPIO access..."

        if [[ -e /dev/spidev0.0 ]]; then
            log_success "SPI: /dev/spidev0.0 available"
        else
            if [[ "$NEEDS_REBOOT" == true ]]; then
                log_warn "SPI: will be available after reboot"
            else
                log_warn "SPI: device not available"
                log_detail "LED ring may not work"
                ((warnings++))
            fi
        fi
    fi

    # Test API connection
    log_info "Testing API connection..."
    local api_url
    api_url=$(grep "^api_url" "${CONFIG_DIR}/hub.toml" 2>/dev/null | cut -d'"' -f2 || echo "http://kagami.local:8001")

    if curl -sSf --connect-timeout 3 "${api_url}/health" > /dev/null 2>&1; then
        log_success "API: ${api_url} reachable"
    else
        log_warn "API: ${api_url} not reachable"
        log_detail "Make sure Kagami API is running"
        ((warnings++))
    fi

    echo ""
    if [[ $errors -gt 0 ]]; then
        log_error "Installation verification failed with $errors error(s)"
        return 1
    elif [[ $warnings -gt 0 ]]; then
        log_warn "Installation complete with $warnings warning(s)"
    else
        log_success "All verification checks passed!"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print_summary() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}${BOLD}                    INSTALLATION COMPLETE!${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""

    if [[ "$NEEDS_REBOOT" == true ]]; then
        echo -e "${YELLOW}${BOLD}REBOOT REQUIRED${NC}"
        echo ""
        echo -e "  GPIO/SPI settings were changed. Please reboot to enable them:"
        echo ""
        echo -e "  ${WHITE}sudo reboot${NC}"
        echo ""
        echo -e "  After reboot, start the hub with:"
        echo ""
        echo -e "  ${WHITE}sudo systemctl start kagami-hub${NC}"
        echo ""
    else
        echo -e "${GREEN}${BOLD}READY TO START${NC}"
        echo ""
        echo -e "  Start the hub now:"
        echo ""
        echo -e "  ${WHITE}sudo systemctl start kagami-hub${NC}"
        echo ""
    fi

    echo -e "${BLUE}USEFUL COMMANDS:${NC}"
    echo ""
    echo -e "  ${DIM}Check status:${NC}  sudo systemctl status kagami-hub"
    echo -e "  ${DIM}View logs:${NC}     journalctl -u kagami-hub -f"
    echo -e "  ${DIM}Edit config:${NC}   sudo nano ${CONFIG_DIR}/hub.toml"
    echo -e "  ${DIM}Restart:${NC}       sudo systemctl restart kagami-hub"
    echo -e "  ${DIM}Stop:${NC}          sudo systemctl stop kagami-hub"
    echo ""

    echo -e "${BLUE}NEXT STEPS:${NC}"
    echo ""
    echo -e "  1. Connect your microphone (USB recommended)"
    echo -e "  2. Connect your speaker"
    echo -e "  3. Wire your LED ring (GPIO18/SPI)"
    echo -e "  4. Start the service"
    echo -e "  5. Say \"Hey Kagami\" and watch the magic!"
    echo ""

    echo -e "${BLUE}WEB INTERFACE:${NC}"
    echo ""
    echo -e "  After starting, access the web interface at:"
    echo -e "  ${WHITE}http://$(hostname).local:8080${NC}"
    echo ""

    echo -e "${BLUE}PHONE APP:${NC}"
    echo ""
    echo -e "  The hub will be auto-discovered by the Kagami iOS/Android apps."
    echo -e "  Look for \"${WHITE}Kagami Hub${NC}\" in the app's Hub section."
    echo ""

    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "         ${WHITE}鏡${NC} — The mirror listens. The mirror responds."
    echo -e "              ${DIM}h(x) >= 0. Always.${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# ═══════════════════════════════════════════════════════════════════════════════
# UPGRADE PATH
# ═══════════════════════════════════════════════════════════════════════════════

handle_existing_install() {
    if [[ "$EXISTING_INSTALL" != true ]]; then
        return 0
    fi

    echo ""
    echo -e "${YELLOW}Existing installation detected!${NC}"
    echo ""
    echo -e "  Current version: ${WHITE}${EXISTING_VERSION:-unknown}${NC}"
    echo -e "  Install location: ${WHITE}${INSTALL_DIR}${NC}"
    echo ""
    echo "What would you like to do?"
    echo ""
    echo "  1) Upgrade (keep configuration)"
    echo "  2) Fresh install (backup old config)"
    echo "  3) Cancel"
    echo ""

    read -r -p "$(echo -e "${CYAN}Choice${NC} [1]: ")" choice
    choice="${choice:-1}"

    case "$choice" in
        1)
            log_info "Upgrading existing installation..."
            # Stop service if running
            systemctl stop kagami-hub 2>/dev/null || true
            return 0
            ;;
        2)
            log_info "Performing fresh install..."
            # Backup old config
            if [[ -f "${CONFIG_DIR}/hub.toml" ]]; then
                cp "${CONFIG_DIR}/hub.toml" "${CONFIG_DIR}/hub.toml.backup.$(date +%Y%m%d%H%M%S)"
                log_info "Backed up old config"
            fi
            # Stop service if running
            systemctl stop kagami-hub 2>/dev/null || true
            # Remove old installation
            rm -rf "$INSTALL_DIR"
            return 0
            ;;
        3)
            echo ""
            log_info "Installation cancelled."
            exit 0
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

cleanup() {
    spinner_stop
    # Any cleanup needed on exit
}

error_handler() {
    local line_no=$1
    local error_code=$2

    spinner_stop

    echo ""
    log_error "Installation failed at line $line_no (error code: $error_code)"
    echo ""
    echo -e "${YELLOW}TROUBLESHOOTING:${NC}"
    echo ""
    echo "  1. Check your internet connection"
    echo "  2. Make sure you're running as root (sudo)"
    echo "  3. Check available disk space: df -h /"
    echo "  4. Review errors above for specific issues"
    echo ""
    echo "  For help, open an issue at:"
    echo "  https://github.com/kagami/kagami-hub/issues"
    echo ""

    exit "$error_code"
}

trap cleanup EXIT
trap 'error_handler ${LINENO} $?' ERR

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    print_banner

    # Phase 1: Detection
    detect_system

    # Phase 2: Prerequisites
    check_prerequisites

    # Phase 3: Handle existing installation
    handle_existing_install

    # Phase 4: System configuration
    fix_system

    # Phase 5: Download and install
    download_and_install

    # Phase 6: Interactive configuration
    configure_interactive

    # Phase 7: Verification
    verify_installation

    # Phase 8: Summary
    print_summary
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
