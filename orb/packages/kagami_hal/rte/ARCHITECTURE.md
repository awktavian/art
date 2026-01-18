# 鏡 Kagami Real-Time Executor (RTE) Architecture

**The HAL is the VM. The RTE is the Executor. The Protocol is the Bytecode.**

---

## Overview

The Real-Time Executor (RTE) subsystem provides deterministic timing guarantees for hardware I/O operations that Linux cannot reliably perform. It is a **pluggable backend** for the HAL's embedded adapters.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            KAGAMI CORE                                       │
│         UnifiedOrganism · World Model · Active Inference · CBF              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                              SafeHAL                                         │
│                          h(x) ≥ 0 Always                                     │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  All commands checked against CBF before execution                    │  │
│   │  Emergency halt sets h(x) = -∞, blocks everything                     │  │
│   │  Unsafe commands projected to safe set boundary                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                           HAL PROTOCOLS                                      │
│             (The "Instruction Set" of the Hardware VM)                       │
│                                                                              │
│   DisplayAdapter · AudioAdapter · InputAdapter · SensorAdapter               │
│   PowerAdapter · ActuatorAdapter · SEMGAdapter                               │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────────────┐
          │                        │                                │
┌─────────▼─────────┐    ┌─────────▼─────────┐    ┌─────────────────▼─────────┐
│ PLATFORM ADAPTERS │    │  EMBEDDED ADAPTER │    │      VIRTUAL ADAPTER      │
│                   │    │                   │    │                           │
│ macOS, Windows    │    │  Uses RTE Backend │    │  Testing/Simulation       │
│ iOS, Android      │    │  for real-time    │    │  Stubs                    │
│ WASM, VisionOS    │    │  I/O operations   │    │                           │
│ WatchOS, WearOS   │    │                   │    │                           │
└───────────────────┘    └─────────┬─────────┘    └───────────────────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │    RTE PROTOCOL     │
                        │  (Hardware VM       │
                        │   Bytecode)         │
                        │                     │
                        │  PAT:n    LED       │
                        │  BRT:n    Bright    │
                        │  COL:r,g,b Color    │
                        │  AUD:...  Audio     │
                        │  SEN:...  Sensor    │
                        │  PWR:...  Power     │
                        └──────────┬──────────┘
                                   │
     ┌─────────────┬───────────────┼───────────────┬─────────────┐
     │             │               │               │             │
┌────▼────┐  ┌─────▼─────┐  ┌──────▼──────┐  ┌────▼────┐  ┌─────▼─────┐
│  PICO   │  │   ESP32   │  │   NATIVE    │  │  FPGA   │  │  VIRTUAL  │
│   RTE   │  │    RTE    │  │    RTE      │  │   RTE   │  │    RTE    │
│         │  │           │  │             │  │         │  │           │
│ Embassy │  │ ESP-IDF   │  │ Direct      │  │ Verilog │  │ Python    │
│ RP2040  │  │ ESP32-S3  │  │ SPI/I2C     │  │ Ice40   │  │ Stubs     │
│ UART    │  │ WiFi/BLE  │  │ Linux       │  │ <1µs    │  │ Testing   │
│ <10µs   │  │ OTA       │  │ ~10ms       │  │         │  │           │
└─────────┘  └───────────┘  └─────────────┘  └─────────┘  └───────────┘
```

---

## Design Principles

### 1. Single Protocol, Multiple Executors

The RTE Protocol defines a platform-independent "bytecode" that can execute on any backend:

| Backend     | Transport | Latency  | Use Case                  |
|-------------|-----------|----------|---------------------------|
| PicoRTE     | UART      | <10µs    | Production embedded       |
| NativeRTE   | Direct    | ~10ms    | Desktop/high-power        |
| VirtualRTE  | Memory    | 0µs      | Testing/simulation        |
| ESP32RTE    | WiFi/BLE  | ~50ms    | IoT deployment            |
| FPGARTE     | SPI       | <1µs     | Ultra-low-latency         |

### 2. Safety at the Top

CBF safety enforcement happens in SafeHAL, **before** commands reach the RTE:

```python
# SafeHAL checks h(x) >= 0 before ANY actuator command
result = await safe_hal.send_actuation(actuator, command)
if not result.is_safe:
    # Command was blocked or projected to safe set
    pass
```

The RTE layer does NOT perform safety checks — it trusts that SafeHAL has already validated.

### 3. Graceful Degradation

If a preferred RTE backend is unavailable, fall back gracefully:

```
PicoRTE (preferred) → NativeRTE (fallback) → VirtualRTE (stub)
```

This ensures the system always runs, even without hardware.

### 4. Protocol Versioning

The RTE protocol includes version negotiation:

```
VER:1.0\n  →  Request version 1.0
ACK:1.0\n  ←  Server confirms 1.0
```

Breaking changes require major version bump.

---

## Protocol Specification

### Wire Format

```
COMMAND:arg1,arg2,...\n
RESPONSE:data\n
```

- UTF-8 encoded ASCII
- Newline-terminated
- Arguments comma-separated
- No spaces around colons or commas
- Maximum line length: 256 bytes

### Commands (Host → RTE)

| Command | Args           | Description                      |
|---------|----------------|----------------------------------|
| `VER`   | major.minor    | Request protocol version         |
| `PAT`   | pattern_id     | Set LED animation pattern (0-15) |
| `BRT`   | level          | Set brightness (0-255)           |
| `COL`   | r,g,b          | Set override color               |
| `FRM`   | hex_data       | Raw LED frame (12 RGB bytes)     |
| `AUD`   | cmd,args...    | Audio subsystem command          |
| `SEN`   | sensor_id      | Read sensor value                |
| `PWR`   | mode           | Set power mode (0=normal,1=low)  |
| `PNG`   | -              | Ping (heartbeat)                 |
| `STS`   | -              | Request status                   |
| `RST`   | -              | Reset to defaults                |

### Responses (RTE → Host)

| Response | Data                      | Description               |
|----------|---------------------------|---------------------------|
| `ACK`    | version                   | Version acknowledgement   |
| `PON`    | -                         | Pong (heartbeat response) |
| `STS`    | pattern,brightness,frames | Status response           |
| `SEN`    | sensor_id,value           | Sensor reading            |
| `BTN`    | -                         | Button pressed event      |
| `ERR`    | code                      | Error occurred            |
| `OK`     | -                         | Command succeeded         |

### Error Codes

| Code | Meaning                    |
|------|----------------------------|
| 1    | Unknown command            |
| 2    | Invalid arguments          |
| 3    | Hardware failure           |
| 4    | Timeout                    |
| 5    | Buffer overflow            |
| 6    | Version mismatch           |

---

## LED Animation Patterns

| ID | Name             | Description                           |
|----|------------------|---------------------------------------|
| 0  | Idle             | Static colony colors                  |
| 1  | Breathing        | Slow ambient pulse                    |
| 2  | Spin             | Rotating chase                        |
| 3  | Pulse            | Center-out pulse (listening)          |
| 4  | Cascade          | Waterfall effect (executing)          |
| 5  | Flash            | Quick green flash (success)           |
| 6  | ErrorFlash       | Quick red flash (error)               |
| 7  | Rainbow          | HSV rotation                          |
| 8  | Spectral         | Prism refraction                      |
| 9  | FanoPulse        | Fano plane geometry                   |
| 10 | SpectralSweep    | Color sweep across ring               |
| 11 | ChromaticSuccess | Green chromatic confirmation          |
| 12 | ChromaticError   | Red chromatic alert                   |
| 13 | SafetySafe       | Green safety indicator (h(x) > 0.5)   |
| 14 | SafetyCaution    | Yellow caution (0 < h(x) ≤ 0.5)       |
| 15 | SafetyViolation  | Red violation (h(x) ≤ 0)              |

### Colony-LED Mapping (12 LEDs)

```
       LED 0 (Spark, Red)
   LED 11              LED 1
      ╲                  ╱
       ╲    LED Ring    ╱
        ◆──────────────◆
       ╱ ╲            ╱ ╲
  LED 10   ╲        ╱   LED 2 (Forge, Orange)
            ╲      ╱
    LED 9────◆────◆────LED 3
            ╱      ╲
  LED 8   ╱        ╲   LED 4 (Flow, Gold)
       ╱ ╱            ╲ ╲
        ◆──────────────◆
       ╱                ╲
   LED 7              LED 5
       LED 6 (Nexus, Green)
```

| LED Index | Colony  | RGB Color       |
|-----------|---------|-----------------|
| 0, 11     | Spark   | (232, 33, 39)   |
| 1, 2      | Forge   | (247, 148, 29)  |
| 3, 4      | Flow    | (255, 199, 44)  |
| 5, 6      | Nexus   | (0, 166, 81)    |
| 7, 8      | Beacon  | (0, 174, 239)   |
| 9         | Grove   | (146, 39, 143)  |
| 10        | Crystal | (237, 30, 121)  |

---

## Implementation Files

```
kagami_hal/rte/
├── __init__.py          # Public API exports
├── ARCHITECTURE.md      # This document
├── protocol.py          # RTECommand enum, RTEBackend protocol
├── pico.py              # PicoRTE implementation (UART)
├── native.py            # NativeRTE implementation (direct)
├── virtual.py           # VirtualRTE implementation (testing)
└── types.py             # RTEStatus, RTEEvent dataclasses
```

---

## Usage Examples

### Basic Usage

```python
from kagami_hal.rte import PicoRTE, NativeRTE, VirtualRTE, RTECommand

# Production: Use Pico coprocessor
rte = PicoRTE("/dev/ttyACM0")
await rte.initialize()

# Set LED pattern
await rte.send_command(RTECommand.LED_PATTERN, 1)  # Breathing

# Get status
status = await rte.get_status()
print(f"Pattern: {status.pattern}, Brightness: {status.brightness}")
```

### With Fallback

```python
from kagami_hal.rte import get_rte_backend

# Auto-selects best available backend
rte = await get_rte_backend()  # Pico → Native → Virtual

await rte.send_command(RTECommand.LED_BRIGHTNESS, 200)
```

### In Embedded Adapter

```python
from kagami_hal.adapters.embedded import EmbeddedLED
from kagami_hal.rte import PicoRTE

class EmbeddedLED:
    def __init__(self, rte: RTEBackend = None):
        self.rte = rte or PicoRTE.auto_discover()

    async def set_pattern(self, pattern: int):
        await self.rte.send_command(RTECommand.LED_PATTERN, pattern)
```

---

## Safety Invariants

1. **h(x) ≥ 0 Always** — SafeHAL enforces this before RTE sees any command
2. **RTE does not validate** — It trusts the upper layers
3. **Emergency halt** — SafeHAL can set h(x) = -∞ to block all commands
4. **Graceful degradation** — System always runs, even without RTE hardware

---

## Hardware Requirements

### Pico RTE (RP2040)

- Raspberry Pi Pico or Pico W
- 133MHz dual-core ARM Cortex-M0+
- Embassy RTOS (Rust async runtime)
- WS2812B LED ring (12 LEDs recommended)
- UART connection to host (115200 baud)
- Optional: I2S for audio, GPIO for buttons

### Wiring

```
Raspberry Pi              Pico
───────────────────────────────────
GPIO 14 (TXD) ────────── GPIO 1 (RX)
GPIO 15 (RXD) ────────── GPIO 0 (TX)
GND ──────────────────── GND
5V ───────────────────── VBUS (power)

Pico                     LED Ring
───────────────────────────────────
GPIO 16 ─────────────────── DIN
GND ─────────────────────── GND
VBUS ────────────────────── VCC (5V)

Pico                     Button
───────────────────────────────────
GPIO 17 ─────────────────── One side
GND ─────────────────────── Other side
```

---

## Performance Targets

| Metric                  | Target    | PicoRTE  | NativeRTE |
|-------------------------|-----------|----------|-----------|
| LED frame latency       | <1ms      | <100µs   | ~10ms     |
| Button response         | <10ms     | <1ms     | ~20ms     |
| Command round-trip      | <50ms     | <5ms     | <1ms      |
| Animation frame rate    | 60fps     | 60fps    | 30fps     |
| Audio I2S jitter        | <10µs     | <1µs     | N/A       |

---

## Future Extensions

1. **ESP32RTE** — WiFi/BLE transport for IoT deployment
2. **FPGARTE** — Ultra-low-latency for professional audio
3. **ClusterRTE** — Multiple RTEs synchronized via mesh
4. **AudioRTE** — Dedicated audio I2S commands

---

## References

- [Embassy RTOS](https://embassy.dev/)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [WS2812B Protocol](https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf)
- [Kagami HAL Architecture](/packages/kagami_hal/README.md)
- [SafeHAL Safety Layer](/packages/kagami_hal/interface/safe_hal.py)

---

**鏡**

*The HAL is the VM. The RTE is the Executor.*
*The Protocol is the Bytecode. Safety is the Invariant.*

*h(x) ≥ 0. Always.*
