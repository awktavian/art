#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# KAGAMI HUB INSTALLATION SCRIPT
# Colony: Forge (e₂) — Deployment infrastructure
#
# Automated installation of Kagami Hub on Raspberry Pi (Debian/Ubuntu).
# Sets up systemd services, configuration, and cluster integration.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/kagami/kagami/main/deploy/scripts/install-hub.sh | sudo bash
#
# Or with custom options:
#   sudo ./install-hub.sh --hub-name "Living Room" --api-url "http://192.168.1.100:8001"
#
# Requirements:
#   - Raspberry Pi with Debian/Ubuntu (64-bit recommended)
#   - Audio hardware (USB mic, speakers)
#   - Network connectivity
#   - sudo privileges
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Default configuration
HUB_NAME="${HUB_NAME:-Kagami Hub}"
API_URL="${API_URL:-http://kagami.local:8001}"
INSTALL_DIR="${INSTALL_DIR:-/opt/kagami-hub}"
KAGAMI_USER="${KAGAMI_USER:-kagami}"
KAGAMI_GROUP="${KAGAMI_GROUP:-kagami}"

# Release info
RELEASE_URL="https://github.com/kagami/kagami-hub/releases/latest/download"
BINARY_NAME="kagami-hub"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ═══════════════════════════════════════════════════════════════════════════
# Parse Arguments
# ═══════════════════════════════════════════════════════════════════════════

while [[ $# -gt 0 ]]; do
    case $1 in
        --hub-name)
            HUB_NAME="$2"
            shift 2
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --user)
            KAGAMI_USER="$2"
            shift 2
            ;;
        -h|--help)
            echo "Kagami Hub Installation Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --hub-name NAME      Set hub display name (default: 'Kagami Hub')"
            echo "  --api-url URL        Set API server URL (default: 'http://kagami.local:8001')"
            echo "  --install-dir DIR    Installation directory (default: '/opt/kagami-hub')"
            echo "  --user USER          System user (default: 'kagami')"
            echo "  -h, --help           Show this help"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════
# Pre-flight Checks
# ═══════════════════════════════════════════════════════════════════════════

log_info "Starting Kagami Hub installation..."
log_info "Hub Name: $HUB_NAME"
log_info "API URL: $API_URL"
log_info "Install Dir: $INSTALL_DIR"

# Check root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (sudo)"
    exit 1
fi

# Check architecture
ARCH=$(uname -m)
case $ARCH in
    aarch64|arm64)
        BINARY_ARCH="aarch64-unknown-linux-gnu"
        ;;
    armv7l|armhf)
        BINARY_ARCH="armv7-unknown-linux-gnueabihf"
        ;;
    x86_64)
        BINARY_ARCH="x86_64-unknown-linux-gnu"
        ;;
    *)
        log_error "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac
log_info "Architecture: $ARCH ($BINARY_ARCH)"

# ═══════════════════════════════════════════════════════════════════════════
# Install Dependencies
# ═══════════════════════════════════════════════════════════════════════════

log_info "Installing system dependencies..."
apt-get update -qq

apt-get install -y -qq \
    alsa-utils \
    pulseaudio \
    avahi-daemon \
    avahi-utils \
    libasound2-dev \
    libpulse-dev \
    curl \
    wget \
    jq

# Enable mDNS
systemctl enable avahi-daemon
systemctl start avahi-daemon

log_success "Dependencies installed"

# ═══════════════════════════════════════════════════════════════════════════
# Create User and Directories
# ═══════════════════════════════════════════════════════════════════════════

log_info "Creating user and directories..."

# Create user if doesn't exist
if ! id "$KAGAMI_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$INSTALL_DIR" -m "$KAGAMI_USER"
    log_info "Created user: $KAGAMI_USER"
fi

# Add user to required groups
usermod -a -G audio,gpio,spi,i2c,video "$KAGAMI_USER" 2>/dev/null || true

# Create directories
mkdir -p "$INSTALL_DIR"/{config,logs,bin}
chown -R "$KAGAMI_USER:$KAGAMI_GROUP" "$INSTALL_DIR"

log_success "Directories created"

# ═══════════════════════════════════════════════════════════════════════════
# Download and Install Binary
# ═══════════════════════════════════════════════════════════════════════════

log_info "Downloading Kagami Hub binary..."

BINARY_URL="${RELEASE_URL}/${BINARY_NAME}-${BINARY_ARCH}"
TEMP_BINARY="/tmp/kagami-hub"

if curl -sSL -o "$TEMP_BINARY" "$BINARY_URL"; then
    chmod +x "$TEMP_BINARY"
    mv "$TEMP_BINARY" /usr/local/bin/kagami-hub
    log_success "Binary installed to /usr/local/bin/kagami-hub"
else
    log_warn "Failed to download binary. Building from source may be required."
    log_warn "See https://github.com/kagami/kagami-hub for build instructions."
fi

# ═══════════════════════════════════════════════════════════════════════════
# Generate Configuration
# ═══════════════════════════════════════════════════════════════════════════

log_info "Generating configuration..."

# Generate unique hub ID
HUB_ID="hub-$(hostname)-$(date +%s | sha256sum | head -c 8)"

cat > "$INSTALL_DIR/config/hub.toml" << EOF
# Kagami Hub Configuration
# Generated: $(date -Iseconds)

[hub]
id = "$HUB_ID"
name = "$HUB_NAME"

[api]
url = "$API_URL"
timeout_seconds = 5
retry_attempts = 3

[mesh]
enabled = true
ws_port = 9877
mdns_enabled = true
heartbeat_interval_ms = 5000
peer_timeout_ms = 15000

[crdt]
sync_interval_ms = 10000

[byzantine]
detection_enabled = true
fault_threshold = 3
decay_interval_seconds = 300

[audio]
# Auto-detect default devices
input_device = "default"
output_device = "default"
sample_rate = 16000
channels = 1

[wake_word]
enabled = true
sensitivity = 0.5
models = ["hey_kagami"]

[led_ring]
enabled = true
spi_device = "/dev/spidev0.0"
num_leds = 12
brightness = 0.5

[logging]
level = "info"
file = "$INSTALL_DIR/logs/hub.log"
max_size_mb = 10
max_files = 5
EOF

chown "$KAGAMI_USER:$KAGAMI_GROUP" "$INSTALL_DIR/config/hub.toml"

log_success "Configuration generated: $INSTALL_DIR/config/hub.toml"

# ═══════════════════════════════════════════════════════════════════════════
# Install Systemd Service
# ═══════════════════════════════════════════════════════════════════════════

log_info "Installing systemd service..."

cat > /etc/systemd/system/kagami-hub.service << EOF
# Kagami Hub Service — Generated by install-hub.sh
# $(date -Iseconds)

[Unit]
Description=Kagami Hub — $HUB_NAME
Documentation=https://github.com/kagami/kagami-hub
After=network-online.target sound.target avahi-daemon.service
Wants=network-online.target avahi-daemon.service
Requires=sound.target

[Service]
Type=notify
User=$KAGAMI_USER
Group=$KAGAMI_GROUP
WorkingDirectory=$INSTALL_DIR

Environment="RUST_LOG=info,kagami_hub=debug"
Environment="KAGAMI_HUB_CONFIG=$INSTALL_DIR/config/hub.toml"
Environment="KAGAMI_API_URL=$API_URL"
Environment="ALSA_CARD=default"

ExecStart=/usr/local/bin/kagami-hub
ExecReload=/bin/kill -HUP \$MAINPID

Restart=on-failure
RestartSec=10s
WatchdogSec=30

LimitNOFILE=65536
LimitMEMLOCK=infinity

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
PrivateDevices=false

SupplementaryGroups=audio gpio spi i2c video

ReadWritePaths=$INSTALL_DIR/config
ReadWritePaths=$INSTALL_DIR/logs
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

log_success "Systemd service installed"

# ═══════════════════════════════════════════════════════════════════════════
# Audio Configuration
# ═══════════════════════════════════════════════════════════════════════════

log_info "Configuring audio..."

# Set default ALSA card (if multiple)
if [ -f /etc/asound.conf ]; then
    cp /etc/asound.conf /etc/asound.conf.backup
fi

cat > /etc/asound.conf << 'EOF'
# Kagami Hub Audio Configuration
pcm.!default {
    type asym
    playback.pcm "plughw:0,0"
    capture.pcm "plughw:0,0"
}
ctl.!default {
    type hw
    card 0
}
EOF

log_success "Audio configured"

# ═══════════════════════════════════════════════════════════════════════════
# Final Steps
# ═══════════════════════════════════════════════════════════════════════════

log_info "Running final setup..."

# Enable SPI (for LED ring)
if [ -f /boot/config.txt ]; then
    if ! grep -q "dtparam=spi=on" /boot/config.txt; then
        echo "dtparam=spi=on" >> /boot/config.txt
        log_info "Enabled SPI in /boot/config.txt (reboot required)"
    fi
fi

# Start the service
log_info "Starting Kagami Hub service..."
systemctl start kagami-hub

# Wait for startup
sleep 3

# Check status
if systemctl is-active --quiet kagami-hub; then
    log_success "Kagami Hub is running!"
else
    log_warn "Service may not have started. Check: journalctl -u kagami-hub -f"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
log_success "Kagami Hub installation complete!"
echo ""
echo "  Hub ID:      $HUB_ID"
echo "  Hub Name:    $HUB_NAME"
echo "  API URL:     $API_URL"
echo "  Install Dir: $INSTALL_DIR"
echo ""
echo "Commands:"
echo "  sudo systemctl status kagami-hub    # Check status"
echo "  sudo journalctl -u kagami-hub -f    # View logs"
echo "  sudo systemctl restart kagami-hub   # Restart"
echo ""
echo "Configuration: $INSTALL_DIR/config/hub.toml"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "鏡 — The Hub awakens. The mesh awaits."
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# 鏡
# The Hub is deployed. The mesh grows.
# h(x) ≥ 0. Always.
# ═══════════════════════════════════════════════════════════════════════════
