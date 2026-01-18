# 鏡 Kagami Pico — Real-Time Coprocessor

Embassy-based RTOS firmware for the Raspberry Pi Pico (RP2040) that handles real-time I/O tasks that Linux cannot perform deterministically.

## Why a Coprocessor?

| Task | Linux (Tokio) | RTOS (Embassy) |
|------|---------------|----------------|
| LED Ring (60fps) | ~10ms jitter | ~10µs jitter |
| Audio I2S | Buffer underruns | DMA, sample-accurate |
| Button Input | ~10ms latency | ~100µs latency |
| Power Management | Always on | Deep sleep modes |

The Pico handles:
- **LED Ring**: 7 WS2812 LEDs via PIO (programmable I/O)
- **Audio I2S**: Sample-accurate microphone capture (planned)
- **Buttons**: Low-latency GPIO input with interrupts
- **Safety Status**: Visual h(x) indicator

The Raspberry Pi handles:
- AI inference (Whisper STT, Piper TTS)
- SQLite database
- WebSocket connections
- Mesh networking
- Complex business logic

## Hardware Setup

```
Raspberry Pi 4/5          Raspberry Pi Pico
┌─────────────────┐       ┌─────────────────┐
│                 │       │                 │
│ UART TX (GPIO14)├───────┤ RX (GP1)        │
│ UART RX (GPIO15)├───────┤ TX (GP0)        │
│ GND             ├───────┤ GND             │
│ 5V              ├───────┤ VBUS (optional) │
│                 │       │                 │
│                 │       │ GP16 ──── LED Ring Data
│                 │       │ GP15 ──── Button
│                 │       │                 │
└─────────────────┘       └─────────────────┘
```

## Protocol

Simple ASCII protocol over UART (115200 baud):

### Commands (Pi → Pico)

| Command | Args | Description |
|---------|------|-------------|
| `PAT:n` | n=0-15 | Set LED pattern |
| `BRT:n` | n=0-255 | Set brightness |
| `COL:r,g,b` | 0-255 each | Set override color |
| `PNG` | - | Ping (heartbeat) |
| `STS` | - | Request status |

### Responses (Pico → Pi)

| Response | Data | Description |
|----------|------|-------------|
| `PON` | - | Pong (heartbeat response) |
| `STS:p,b,f` | pattern,brightness,frames | Status |
| `BTN` | - | Button pressed |
| `ERR:n` | error code | Error occurred |

## LED Patterns

| ID | Pattern | Description |
|----|---------|-------------|
| 0 | Idle | Colony colors at steady brightness |
| 1 | Breathing | Slow sinusoidal brightness |
| 2 | Spin | Rotating for processing |
| 3 | Pulse | Fast pulse for listening |
| 4 | Cascade | Outward wave for executing |
| 5 | Flash | Green success flash |
| 6 | ErrorFlash | Red error flash |
| 7 | Rainbow | HSV rainbow chase |
| 8 | Spectral | Color sweep through colonies |
| 9 | FanoPulse | Phase-offset breathing |
| 10 | SpectralSweep | Physics-accurate ROYGBIV |
| 11 | ChromaticSuccess | Warm pulse (success) |
| 12 | ChromaticError | Cool pulse (error) |
| 13 | SafetySafe | Green (h(x) ≥ 0.5) |
| 14 | SafetyCaution | Yellow (0 ≤ h(x) < 0.5) |
| 15 | SafetyViolation | Red (h(x) < 0) |

## Building

### Prerequisites

```bash
# Install Rust embedded toolchain
rustup target add thumbv6m-none-eabi

# Install probe-rs for flashing
cargo install probe-rs --features cli

# Install flip-link for improved debugging
cargo install flip-link
```

### Build and Flash

```bash
# Build in release mode
cargo build --release

# Flash to Pico (with debug probe)
cargo run --release

# Or using UF2 (drag-and-drop):
cargo objcopy --release -- -O binary kagami-pico.bin
# Convert to UF2 and copy to Pico in bootloader mode
```

## Development

### Running Tests

```bash
# Run on host (stub implementation)
cargo test --target x86_64-unknown-linux-gnu
```

### Debugging

```bash
# With RTT (Real-Time Transfer) logging
DEFMT_LOG=debug cargo run --release
```

## Integration with Kagami Hub

On the Pi side, use `PicoClient`:

```rust
use kagami_hub::pico_client::{PicoClient, Pattern};

async fn main() {
    // Connect to Pico
    let pico = PicoClient::new("/dev/ttyACM0").await?;

    // Show breathing pattern
    pico.show_breathing().await?;

    // Show safety status based on h(x)
    pico.show_safety(0.8).await?; // Green (safe)
    pico.show_safety(0.3).await?; // Yellow (caution)
    pico.show_safety(-0.1).await?; // Red (violation)

    // Ping for heartbeat
    assert!(pico.ping().await?);
}
```

## Colony Colors

The 7 LEDs represent the 7 colonies of Kagami:

| LED | Colony | Color | Wavelength |
|-----|--------|-------|------------|
| 0 | Spark (e₁) | Red | 620nm |
| 1 | Forge (e₂) | Orange | 590nm |
| 2 | Flow (e₃) | Yellow | 570nm |
| 3 | Nexus (e₄) | Green | 510nm |
| 4 | Beacon (e₅) | Cyan | 475nm |
| 5 | Grove (e₆) | Blue | 445nm |
| 6 | Crystal (e₇) | Violet | 400nm |

---

```
鏡
Real-time through Embassy. Deterministic through PIO.
The LED ring breathes with the home.

h(x) ≥ 0. Always.
```
