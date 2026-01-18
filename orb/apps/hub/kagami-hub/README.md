# 鏡 Kagami Hub

**Voice-First Embedded Home Assistant**

A Raspberry Pi-based always-listening AI assistant inspired by HAL 9000.

## Features

- **Wake Word Detection** — "Hey Kagami" using Porcupine or Vosk
- **Speech-to-Text** — Local Whisper transcription
- **Smart Home Control** — Full integration with Kagami API
- **LED Ring** — 7 LEDs showing colony status (one for each e₁-e₇)
- **Voice Response** — TTS via Kagami API's Parler-TTS
- **Phone Integration** — Configure and control from iOS/Android apps
- **mDNS Discovery** — Auto-discovered as `_kagami-hub._tcp`

## Hardware Requirements

- Raspberry Pi 4 (4GB+ recommended)
- USB Microphone or I2S MEMS mic
- WS2812B LED ring (7 LEDs)
- Speaker (3.5mm or I2S DAC)
- Optional: E-ink or LCD display

## Wiring

### LED Ring (WS2812B)
```
LED Ring → Pi
VCC      → 5V
GND      → GND
DIN      → GPIO18 (SPI MOSI)
```

### I2S Microphone (optional)
```
Mic      → Pi
VCC      → 3.3V
GND      → GND
BCLK     → GPIO18
LRCLK    → GPIO19
DOUT     → GPIO20
```

## Installation

### Quick Install (Raspberry Pi)

Run the automated installer:

```bash
# Clone
git clone https://github.com/kagami/kagami-hub
cd kagami-hub/apps/hub/kagami-hub

# Run installer (requires sudo)
sudo ./scripts/install.sh
```

The installer will:
1. Install system dependencies (ALSA, SSL, build tools)
2. Create a `kagami` service user
3. Configure GPIO/SPI permissions for LED ring
4. Download AI models (Whisper STT, Piper TTS)
5. Build and install the binary
6. Set up systemd service

After installation, reboot to enable GPIO access, then start:

```bash
sudo systemctl start kagami-hub
```

### Manual Installation

```bash
# Clone
git clone https://github.com/kagami/kagami-hub
cd kagami-hub

# Build (choose features based on platform)
cargo build --release --features rpi      # Raspberry Pi
cargo build --release --features desktop  # Desktop development

# Configure
cp config/hub.example.toml config/hub.toml
# Edit config/hub.toml with your settings

# Run
./target/release/kagami-hub
```

### Feature Flags

| Feature | Description |
|---------|-------------|
| `rpi` | Raspberry Pi GPIO support (LED ring, hardware buttons) |
| `mdns` | mDNS service discovery for phone apps |
| `whisper` | Local Whisper STT (requires model files) |
| `piper` | Piper TTS for local voice synthesis |
| `audio` | Cross-platform audio I/O (cpal) |
| `hub-hardware` | Full production build (rpi + mdns + whisper + piper + audio) |
| `desktop` | Development build (mdns + audio + whisper + piper) |

## Configuration

Edit `config/hub.toml`:

```toml
[general]
name = "Kagami Hub"
location = "Living Room"
api_url = "http://kagami.local:8001"

[wake_word]
engine = "porcupine"
sensitivity = 0.5
phrase = "Hey Kagami"

[led_ring]
enabled = true
count = 7
pin = 18
brightness = 0.5
```

## Voice Commands

After saying "Hey Kagami":

| Command | Action |
|---------|--------|
| "Movie mode" | Enter home theater mode |
| "Goodnight" | Execute goodnight routine |
| "Welcome home" | Execute welcome routine |
| "Lights [off/25/50/100]" | Control lights |
| "Lights off in kitchen" | Room-specific control |
| "Fireplace on/off" | Toggle fireplace |
| "Shades open/close" | Control shades |
| "TV up/down" | MantelMount control |
| "Announce [message]" | TTS announcement |

## LED Ring States

| State | Pattern |
|-------|---------|
| Idle | Colony colors cycling slowly |
| Listening | Blue pulse (Flow/e₃) |
| Processing | Purple spin (Nexus/e₄) |
| Success | Green flash |
| Error | Red flash |
| Safety OK | Soft green glow |
| Safety Caution | Yellow glow |
| Safety Violation | Red pulse |

## Phone Integration

The Hub runs a web server on port 8080 that enables configuration and control from the iOS and Android Kagami apps.

### Discovery

The Hub advertises itself via mDNS as `_kagami-hub._tcp.local`. The phone apps will automatically discover Hubs on your network.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Hub status (safety score, colonies, uptime) |
| `/health` | GET | Health check |
| `/config` | GET/POST | Read/update Hub configuration |
| `/led` | POST | Control LED ring pattern |
| `/led/test` | POST | Run LED test pattern |
| `/voice/proxy` | POST | Send audio from phone to Hub |
| `/voice/listen` | POST | Trigger wake word listening |
| `/command` | POST | Execute voice command |
| `/ws` | WebSocket | Real-time status updates |

### Voice Proxy

When you're away from the Hub but still on your network, you can use your phone as the Hub's "ears":

1. Open the Kagami app → Hub tab
2. Connect to your Hub
3. Tap "Hold to Speak" in Voice Proxy
4. Your voice is sent to the Hub for processing

### Configuration from Phone

All Hub settings can be changed from the phone:
- Hub name and location
- Kagami API URL
- Wake word and sensitivity
- LED ring brightness
- TTS volume and voice style

## Architecture

```
                    ┌─────────────┐
                    │  Microphone │
                    └──────┬──────┘
                           │
                           ▼
┌──────────────────────────────────────────────────┐
│                   Kagami Hub                      │
│                                                   │
│  ┌─────────────┐    ┌──────────────────────────┐ │
│  │  Wake Word  │───▶│     Voice Pipeline       │ │
│  │  Detector   │    │                          │ │
│  └─────────────┘    │  STT → Parser → Execute  │ │
│                     └──────────────────────────┘ │
│         │                      │                 │
│         ▼                      ▼                 │
│  ┌─────────────┐    ┌──────────────────────────┐ │
│  │  LED Ring   │    │      Kagami API          │ │
│  │  Controller │    │  http://kagami:8001      │ │
│  └─────────────┘    └──────────────────────────┘ │
│         │                      │                 │
│         └──────────┬───────────┘                 │
│                    ▼                             │
│         ┌──────────────────────┐                 │
│         │   Phone Web Server   │                 │
│         │   :8080 + mDNS       │                 │
│         └──────────────────────┘                 │
│                    │                             │
└────────────────────┼─────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
┌──────────────────┐  ┌──────────────────┐
│    Smart Home    │  │   iOS/Android    │
│ (Lights, Shades) │  │   Phone Apps     │
└──────────────────┘  └──────────────────┘
```

## Service Installation

```bash
# Copy service file
sudo cp kagami-hub.service /etc/systemd/system/

# Enable and start
sudo systemctl enable kagami-hub
sudo systemctl start kagami-hub

# Check status
sudo systemctl status kagami-hub
```

## Safety

```
h(x) ≥ 0. Always.
```

The LED ring reflects the safety score from the Kagami API.
Any safety violation triggers immediate visual alert.

## Troubleshooting

### LED Ring Not Working

1. **Check SPI is enabled**:
   ```bash
   ls /dev/spidev0.0
   ```
   If not present, add `dtparam=spi=on` to `/boot/config.txt` and reboot.

2. **Check GPIO permissions**:
   ```bash
   groups kagami  # Should include: spi gpio
   ```

3. **Test LED directly**:
   ```bash
   curl -X POST http://localhost:8080/led/test
   ```

### Wake Word Not Detected

1. **Check microphone**:
   ```bash
   arecord -l  # List audio devices
   arecord -d 5 test.wav  # Test recording
   ```

2. **Adjust sensitivity** in `config/hub.toml`:
   ```toml
   [wake_word]
   sensitivity = 0.7  # Increase for noisy environments
   ```

3. **Check audio format**:
   - Required: 16kHz mono for Porcupine/Vosk
   - Check `audio.sample_rate` in config

### API Connection Failed

1. **Check Kagami API is running**:
   ```bash
   curl http://kagami.local:8001/health
   ```

2. **Verify API URL** in config:
   ```toml
   [general]
   api_url = "http://kagami.local:8001"  # Use IP if mDNS fails
   ```

### Phone App Can't Find Hub

1. **Check mDNS is working**:
   ```bash
   avahi-browse -a  # Should show _kagami-hub._tcp
   ```

2. **Check firewall**:
   ```bash
   sudo ufw allow 8080/tcp   # Web server
   sudo ufw allow 5353/udp   # mDNS
   ```

### Service Won't Start

1. **Check logs**:
   ```bash
   journalctl -u kagami-hub -f
   ```

2. **Verify config syntax**:
   ```bash
   /usr/local/bin/kagami-hub --check-config
   ```

3. **Check models exist**:
   ```bash
   ls /opt/kagami-hub/models/  # Should have whisper-base.bin, piper model
   ```

## Development

### Running Tests

```bash
# Unit tests
cargo test

# Integration tests (requires Kagami API mock)
cargo test --test integration_test

# Specific test
cargo test voice_pipeline::tests
```

### Building Documentation

```bash
cargo doc --open --features desktop
```

### Code Style

- Run `cargo fmt` before committing
- Run `cargo clippy` for lints
- Follow existing module patterns

### Adding a New Command Intent

1. Add variant to `CommandIntent` in `src/voice_pipeline.rs`
2. Add parsing logic in `parse_command()`
3. Add API call in `src/api_client.rs`
4. Add LED pattern if appropriate
5. Update tests in `tests/voice_pipeline_test.rs`

### Adding a New LED Pattern

1. Implement pattern in `src/led_ring.rs`
2. Add public wrapper function
3. Add to `control_led` handler in `src/web_server.rs`
4. Add to `VALID_LED_PATTERNS` constant

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`cargo test`)
4. Run lints (`cargo clippy && cargo fmt`)
5. Commit with descriptive message
6. Open a Pull Request

### Areas for Contribution

- **New wake word engines** - Add support for OpenWakeWord, etc.
- **Additional STT engines** - Vosk, custom models
- **LED patterns** - New animations and effects
- **Phone app** - iOS/Android native apps
- **Documentation** - Examples, tutorials, translations

## License

MIT License - see LICENSE file.

---

鏡

*The mirror listens. The mirror responds.*
*Seven lights. Seven colonies. One voice.*
