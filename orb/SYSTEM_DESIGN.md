# Kagami Orb V3.1 System Design

**Version:** 3.1
**Date:** 2026-01-11
**Status:** Design Complete — SEALED 85mm SOTA

---

## Executive Summary

The Kagami Orb V3 is a **levitating AI companion** with a **living eye display** and **hidden camera**. It floats above a walnut base via magnetic levitation, featuring breakthrough interaction through gaze, gesture, and voice.

### V3 Key Specifications

| Aspect | V3 Specification |
|--------|------------------|
| **Form** | 85mm sealed sphere, living eye display |
| **Compute** | QCS6490 (12 TOPS) + Hailo-10H (40 TOPS) = **52 TOPS** |
| **Display** | 1.39" Round AMOLED 454×454 (VERIFIED 38.83×38.21mm module) |
| **Camera** | Sony IMX989 50.3MP hidden in pupil |
| **Runtime** | Tokio async on Linux (NOT Embassy) |
| **Levitation** | HCNT 500g module + custom resonant charging |
| **LEDs** | 16× HD108 16-bit RGBW at equator |
| **Audio** | 4× sensiBel SBM100B optical MEMS (-26dB SNR) + XMOS XVF3800 |
| **Power** | 2200mAh 3S LiPo (24Wh), 15W wireless charging |
| **Thermal** | Sealed passive, base-coupled when docked |
| **Safety** | h(x) ≥ 0 Control Barrier Function |

---

## ✨ "I'M THINKING" + HOVER INTERACTION

### Concept

The base and orb work together to show cognitive state:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DOCKED + PROCESSING                                  │
│                                                                          │
│                          ╭─────────╮                                    │
│                         │  👁️ 🤔  │ ← Orb eye looks "thoughtful"       │
│                          ╰────┬────╯                                    │
│                               │                                          │
│                         ~~ thinking ~~                                   │
│                               │                                          │
│                    ╭──────────┴──────────╮                              │
│                    │   ○ ● ○ ● ○ ● ○ ●  │ ← Base LEDs pulse/chase      │
│                    │    THINKING MODE    │   (purple → blue → purple)   │
│                    ╰─────────────────────╯                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                     HOVER (LIFT OFF BASE)                               │
│                                                                          │
│                          ╭─────────╮                                    │
│                         │  👁️ ✨  │ ← Orb eye brightens, "alert"       │
│                          ╰────┬────╯                                    │
│                               │ ↑ LIFT                                   │
│                        ───────────────                                   │
│                               │                                          │
│                    ╭──────────┴──────────╮                              │
│                    │   ○ ○ ○ ○ ○ ○ ○ ○  │ ← Base fades to soft white    │
│                    │    AMBIENT MODE     │   (warm glow, low power)     │
│                    ╰─────────────────────╯                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### State Machine Extension

| State | Orb Display | Orb LEDs | Base LEDs | Trigger |
|-------|-------------|----------|-----------|---------|
| **Docked Idle** | Eye breathing | Constellation | Soft white pulse | Hall sensor ON |
| **Docked Listening** | Eye wide, pupil dilates | Cyan ring | Steady cyan | Wake word |
| **Docked Thinking** | Eye squints, pupil small | Purple chase | **Purple/blue pulse** | Processing |
| **Docked Speaking** | Eye animated lip-sync | Green pulse | Green follow | TTS active |
| **Hover Transition** | Eye blinks, brightens | White flash | Fade to warm | Hall sensor OFF |
| **Undocked Active** | Eye alert, scanning | Reduced brightness | **Ambient warm glow** | Portable mode |
| **Undocked Thinking** | Eye processing | Purple (dim) | N/A (not docked) | Processing portable |

### Base "Thinking" Animation

```rust
// Base thinking animation (ESP32-S3 firmware)
pub struct ThinkingAnimation {
    phase: f32,
    intensity: f32,
}

impl ThinkingAnimation {
    pub fn tick(&mut self, dt: f32) -> [Rgb; 8] {
        self.phase += dt * 2.0;  // 2 rotations per second

        let mut leds = [Rgb::black(); 8];
        for i in 0..8 {
            let angle = (i as f32 / 8.0) * TAU;
            let wave = ((self.phase + angle).sin() + 1.0) / 2.0;

            // Purple to blue gradient
            let purple = Rgb::new(128, 0, 255);
            let blue = Rgb::new(0, 100, 255);
            leds[i] = purple.lerp(blue, wave) * self.intensity;
        }
        leds
    }
}
```

### Hover Detection → Ambient Mode

```rust
// Hall sensor interrupt on orb lift
pub async fn on_undock(&mut self) {
    // Flash transition
    self.orb_leds.flash_white(100.ms()).await;
    self.eye_display.blink().await;

    // Tell base to go ambient
    self.base_link.send(BaseCommand::AmbientMode {
        color: Rgb::new(255, 200, 150),  // Warm white
        brightness: 0.3,
        pattern: AmbientPattern::SlowBreathing,
    }).await;

    // Orb enters portable mode
    self.transition_to(OrbState::Undocked).await;
}
```

### Base Ambient Mode

```rust
// Soft ambient glow when orb is lifted
pub struct AmbientMode {
    color: Rgb,
    brightness: f32,
    breath_phase: f32,
}

impl AmbientMode {
    pub fn tick(&mut self, dt: f32) -> [Rgb; 8] {
        self.breath_phase += dt * 0.5;  // Slow breathing
        let breath = (self.breath_phase.sin() + 1.0) / 2.0;
        let intensity = self.brightness * (0.7 + 0.3 * breath);

        [self.color * intensity; 8]  // All LEDs same soft glow
    }
}

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │ Voice  │ │  LED   │ │ Power  │ │  API   │ │ State  │       │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   SERVICE LAYER                          │   │
│  │  Safety · Config · Sensors · HAL · Utilities             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   TOKIO ASYNC RUNTIME                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Module Structure

| Module | Purpose | Key Types |
|--------|---------|-----------|
| `state` | State machine & transitions | `OrbState`, `StateEvent`, `Colony` |
| `led` | LED ring control & animations | `LedDriver`, `LedPattern`, `Rgb` |
| `voice` | Audio capture & wake word | `VoicePipeline`, `AudioFrame` |
| `power` | Battery & charging | `PowerManager`, `BatteryState` |
| `api` | WebSocket to kagami-hub | `ApiClient`, `CircuitState` |
| `sensors` | Hall effect, thermal | `HallSensor`, `ThermalMonitor` |
| `hal` | Hardware abstraction | `I2sPeripheral`, `SpiPeripheral` |
| `safety` | h(x) ≥ 0 verification | `SafetyVerifier`, `SafetyResult` |
| `error` | Centralized error taxonomy | `OrbError`, `OrbResult` |
| `util` | Config & timing constants | `OrbConfig`, `timing::*` |

---

## 2. State Machine (V3)

### States

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           V3 STATE MACHINE                                   │
│                                                                              │
│   Startup → Awakening ──┬──→ DockedIdle ⟷ DockedListening → DockedThinking │
│                         │        │              │                │          │
│                         │        ▼              ▼                ▼          │
│                         │    [HOVER]        [HOVER]          [HOVER]        │
│                         │        │              │                │          │
│                         └──→ UndockedIdle ⟷ UndockedListening → Undocked   │
│                                  │              │              Thinking     │
│                                  ▼              ▼                ▼          │
│                              SafetyHalt ← ← Safety ← ← ← ← Safety          │
│                                                                              │
│   [DOCK] transitions: UndockedX → DockedX (instant, flash animation)       │
│   [HOVER] transitions: DockedX → UndockedX (blink, ambient base)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

| State | Description | Orb Eye | Orb LEDs | Base LEDs |
|-------|-------------|---------|----------|-----------|
| `Startup` | Hardware init | Boot animation | Rainbow | Off |
| `Awakening` | First Rise | Eye opens | Bloom | Fade in |
| **`DockedIdle`** | Waiting, charging | Breathing eye | Constellation | Soft white |
| **`DockedListening`** | Wake word detected | Wide eye | Cyan solid | Cyan glow |
| **`DockedThinking`** | Processing AI | Squinting eye | Purple chase | **🔮 Purple pulse** |
| `DockedSpeaking` | TTS output | Animated eye | Green pulse | Green follow |
| **`UndockedIdle`** | Portable standby | Alert eye | Dim constellation | **✨ Ambient warm** |
| **`UndockedListening`** | Portable listening | Wide eye | Dim cyan | Ambient warm |
| **`UndockedThinking`** | Portable processing | Squinting eye | Dim purple | Ambient warm |
| `SafetyHalt` | h(x) < 0 | Red eye | Solid red | Red warning |

### Events

| Event | Trigger | Valid From |
|-------|---------|------------|
| `InitComplete` | HAL ready | Startup |
| `WakeWord` | "Hey Kagami" | Idle |
| `SpeechStart` | VAD detects voice | Listening |
| `SpeechEnd` | Silence timeout | Capturing |
| `ApiResponse` | Response from hub | Processing |
| `Dock` | Hall sensor triggered | Any |
| `Undock` | Hall sensor released | Docked |
| `BatteryLow` | SoC < 20% | Any |
| `BatteryCritical` | SoC < 5% | Any |
| `ThermalWarning` | Temp > 65°C | Any |
| `ThermalCritical` | Temp > 75°C | Any |
| `SafetyViolation` | h(x) < 0 | Any |
| **`PtzCommand`** | Pan/tilt/zoom request | DockedX |
| **`FaceDetected`** | Face enters frame | DockedX |
| **`MotionDetected`** | Motion in FOV | DockedX |
| **`SoundLocalized`** | Beamformer direction | Any |

---

## 🎯 Magnetic PTZ System (Docked Only)

### Overview

When docked, the orb gains **magnetic Pan-Tilt-Zoom control**. The base's torque coil array manipulates the orb's orientation without any mechanical gimbals.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MAGNETIC PTZ CAPABILITIES                            │
│                                                                          │
│   PAN (Yaw):     360° continuous rotation                               │
│   TILT (Pitch):  ±20° forward/backward                                  │
│   ROLL:          ±20° left/right                                        │
│   ZOOM:          1×–10× digital (IMX989)                                │
│                                                                          │
│                         ↺ PAN 360°                                      │
│                              │                                           │
│                        ╭─────┴─────╮                                    │
│                       │     👁️     │                                    │
│                 ↙     │   CAMERA   │     ↘                              │
│            TILT -20°  ╰────────────╯  TILT +20°                         │
│                              │                                           │
│                    ╔═════════╧═════════╗                                │
│                    ║  ◉   MAGLEV   ◉   ║  ← Torque coils               │
│                    ║       BASE        ║                                │
│                    ╚═══════════════════╝                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### PTZ Modes

| Mode | Behavior | Trigger |
|------|----------|---------|
| **Manual** | Direct PTZ commands via API | User/app request |
| **Face Tracking** | Auto-follow detected faces | `FaceDetected` event |
| **Sound Tracking** | Point toward sound source | `SoundLocalized` event |
| **Motion Tracking** | Follow movement in FOV | Security mode |
| **Presentation** | Track display/screen | Presentation mode |
| **Home** | Return to centered, level | Idle timeout or command |

### Coordination with Living Eye

The orb has TWO layers of "looking":

1. **Eye animation** (software) - Pupil/iris can "look" anywhere on display (instant)
2. **PTZ** (physical) - Whole orb rotates to face target (0.5-2 seconds)

```
Person moves across room:
  1. Eye animation IMMEDIATELY tracks (pupil moves on display)
  2. If person moves >30° from center, PTZ kicks in
  3. Orb smoothly pans to re-center person
  4. Eye animation continues fine-tracking

Result: Natural, attentive presence that "looks" at you!
```

### Safety Constraints

PTZ only available when docked (levitation stable). Safety barrier:

```
h_ptz(x) = min(
    1.0 - |pitch + roll| / MAX_TILT,   // Tilt margin
    levitation_force / orb_weight - 1.0, // Lift margin
    1.0 - coil_temp / MAX_TEMP          // Thermal margin
)

If h_ptz(x) < 0 → Emergency level (return to horizontal)
```

See: [hardware/MAGNETIC_PTZ.md](hardware/MAGNETIC_PTZ.md) for full specification

---

## 3. Safety System

### Control Barrier Function

The orb operates under the constraint `h(x) ≥ 0` at all times.

```
h(x) = min(h_thermal(x), h_battery(x), h_levitation(x))

where:
  h_thermal = 1.0 if T < 65°C
            = 0.3×(75-T)/(75-65) if 65 ≤ T < 75
            = -1.0 if T ≥ 75°C

  h_battery = 1.0 if SoC > 20%
            = 0.5×(SoC-5)/(20-5) if 5 < SoC ≤ 20%
            = -1.0 if SoC ≤ 5%
```

### Safety Categories

| Category | h(x) Range | Action |
|----------|------------|--------|
| **Safe** | > 0.5 | Normal operation |
| **Cautious** | 0.2 - 0.5 | Reduce power, warn user |
| **Marginal** | 0 - 0.2 | Minimal operation |
| **Blocked** | ≤ 0 | Halt, enter SafetyHalt state |

### Safety Warnings

| Code | Severity | Message |
|------|----------|---------|
| `ThermalWarning` | 60 | "Temperature approaching limit" |
| `BatteryLow` | 50 | "Battery at X%, consider docking" |
| `LevitationUnstable` | 70 | "Maglev instability detected" |
| `ApiDisconnected` | 40 | "Hub connection lost" |

---

## 4. Hardware Integration

### Qualcomm QCS6490 Pin Mapping

| Function | Interface | GPIO/Pin |
|----------|-----------|----------|
| LED Ring (HD108) | SPI0 MOSI | GPIO36 |
| Microphones (sensiBel SBM100B) | I2S | GPIO45/46/47/48 |
| Speaker (MAX98357A) | I2S | GPIO45/46/48 |
| Thermal (TMP117) | I2C1 | GPIO4/5 |
| Fuel Gauge (BQ40Z50) | I2C1 | GPIO4/5 |
| Hall Sensor (AH49E) | GPIO | GPIO26 |
| Wake Signal | GPIO | GPIO27 |

### Software Dependencies

| Crate | Purpose | Notes |
|-------|---------|-------|
| `tokio` | Async runtime | NOT Embassy (QCS6490 runs Linux) |
| `rpi-pal` | GPIO/SPI/I2C | Maintained fork of rppal |
| `cpal` | Audio I/O | Cross-platform |
| `opus` | Audio encoding | For streaming to hub |
| `whisper-rs` | Local STT | whisper.cpp bindings |
| `smart-leds` | LED protocol | With rpi-ws281x driver |
| `reqwest` | HTTP client | For hub API |
| `tokio-tungstenite` | WebSocket | Real-time streaming |

### Critical Dependency Notes

1. **Embassy vs Tokio**: Embassy is for bare-metal MCUs. QCS6490 runs Linux, so use Tokio.
2. **rppal**: Retired July 2025. Use `rpi-pal` (maintained fork) instead.
3. **VAD**: Use Silero VAD via ONNX runtime for voice activity detection.

---

## 5. LED System

### Colony Colors

| Colony | RGB | Hex | Meaning |
|--------|-----|-----|---------|
| SPARK | (255, 107, 53) | #FF6B35 | Playful, creative |
| FORGE | (255, 179, 71) | #FFB347 | Warm, productive |
| FLOW | (78, 205, 196) | #4ECDC4 | Calm, focused |
| NEXUS | (155, 89, 182) | #9B59B6 | Analytical |
| BEACON | (212, 175, 55) | #D4AF37 | Guiding |
| GROVE | (39, 174, 96) | #27AE60 | Nurturing |
| CRYSTAL | (224, 224, 224) | #E0E0E0 | Clarity |

### Animation Patterns

| Pattern | Parameters | Use Case |
|---------|------------|----------|
| `Solid` | color | Static state |
| `Breathing` | color, period_ms, min/max brightness | Idle |
| `Spinning` | color, period_ms, num_leds | Processing |
| `Pulse` | color, duration_ms | Notifications |
| `Rainbow` | period_ms | Startup |
| `Constellation` | mask, color | Low power |
| `Awakening` | progress, colony_color | First Rise |
| `ColonyBloom` | from, to, progress | Transitions |

### Fibonacci Timing

All animations use Fibonacci-based timing for natural feel:

| Constant | Value | Use |
|----------|-------|-----|
| FIB_89 | 89ms | Micro-interactions |
| FIB_144 | 144ms | Button presses |
| FIB_233 | 233ms | State changes |
| FIB_377 | 377ms | Colony bloom |
| FIB_610 | 610ms | Complex reveals |
| FIB_987 | 987ms | Ambient motion |
| FIB_1597 | 1597ms | Background animations |
| FIB_2584 | 2584ms | Breathing cycle |

---

## 6. Voice Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  MIC ARRAY (4ch) → sensiBel SBM100B DSP → Ring Buffer          │
│        ↓                                                        │
│  Wake Word (openWakeWord/Porcupine)                            │
│        ↓                                                        │
│  VAD (Silero via ONNX)                                         │
│        ↓                                                        │
│  Opus Encoding → WebSocket → kagami-hub                        │
└─────────────────────────────────────────────────────────────────┘
```

### Voice States

| State | Description | LED Pattern |
|-------|-------------|-------------|
| `Idle` | Waiting for wake word | Breathing |
| `Listening` | Wake word detected | Solid FLOW |
| `Capturing` | Recording speech | Fast breathing |
| `Streaming` | Sending to hub | Spinning |
| `Disabled` | Battery conservation | Off |

### Audio Configuration

| Parameter | Value |
|-----------|-------|
| Sample Rate | 16000 Hz |
| Channels | 1 (mono, mixed from 4) |
| Frame Size | 512 samples (32ms) |
| VAD Timeout | 2000ms |
| Wake Word Threshold | 0.6 |

---

## 7. Power Management

### Power Modes

| Mode | CPU MHz | LED Brightness | Features |
|------|---------|----------------|----------|
| Active | 1500 | 100% | Full |
| Idle | 600 | 30% | Wake word only |
| Portable | 1000 | 15% | Reduced features |
| LowPower | 600 | 10% | Minimal |
| Emergency | 400 | 0% | None |

### Battery Thresholds

| Level | SoC | Action |
|-------|-----|--------|
| Full | 100% | Normal |
| Normal | 21-99% | Normal |
| Low | 6-20% | Warning, reduce power |
| Critical | ≤5% | SafetyHalt |

---

## 8. API Integration

### Circuit Breaker Pattern

```
Closed → (5 failures) → Open → (30s timeout) → HalfOpen → (success) → Closed
                                                    ↓
                                              (failure) → Open
```

### WebSocket Protocol

| Direction | Message | Purpose |
|-----------|---------|---------|
| Orb → Hub | `heartbeat` | Keep-alive every 30s |
| Orb → Hub | `state_report` | State changes |
| Orb → Hub | `audio_stream` | Opus frames |
| Hub → Orb | `command` | Actions to execute |
| Hub → Orb | `response` | Speech synthesis text |
| Hub → Orb | `led_pattern` | Override LED display |

---

## 9. Error Taxonomy

### Error Hierarchy

```
OrbError (top-level)
├── ApiError (network/API)
├── PowerError (battery/charging)
├── SensorError (I2C sensors)
├── ConfigError (configuration)
├── StateError (state machine)
├── HalError (hardware)
├── LedError (LED driver)
└── VoiceError (audio pipeline)
```

### Error Handling Strategy

1. **Recoverable errors** → Log, retry with backoff
2. **Transient errors** → Open circuit breaker, queue for later
3. **Safety errors** → Transition to SafetyHalt immediately
4. **Fatal errors** → Log, transition to FatalError, require manual reset

---

## 10. Testing Strategy

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| state | 14 | State transitions, safety |
| led | 7 | Colors, patterns, animations |
| safety | 5 | h(x) computation, categories |
| power | 3 | Modes, dock handling |
| sensors | 2 | Temperature, thresholds |
| api | 3 | Circuit breaker |
| util | 2 | Config, Fibonacci |
| voice | 3 | Pipeline states |
| error | 3 | Display, conversion |
| **Total** | **41** | All pass |

### Test Execution

```bash
# Development - affected tests only
make test-smart

# Full suite
cargo test --features desktop

# CI verification
cargo clippy && cargo test && cargo doc
```

---

## 11. Deployment

### Build Targets

| Target | Feature | Purpose |
|--------|---------|---------|
| `x86_64-apple-darwin` | `desktop` | Development |
| `aarch64-unknown-linux-gnu` | `raspberry-pi` | Production |

### Cross-Compilation

```bash
# Install target
rustup target add aarch64-unknown-linux-gnu

# Build for Pi
cross build --release --target aarch64-unknown-linux-gnu --features raspberry-pi

# Deploy
scp target/aarch64-unknown-linux-gnu/release/kagami-orb pi@kagami-orb.local:
```

---

## 12. Manufacturing Considerations

### BOM Summary

| Quantity | Unit Cost | Tooling | Total |
|----------|-----------|---------|-------|
| 1 (Prototype) | $335 | - | $335 |
| 10 (Dev Kit) | $259 | - | $2,590 |
| 100 (Pilot) | $195 | $7,000 | $26,500 |
| 500 (Production) | $135 | $12,000 | $79,500 |

### Critical Path

1. **Maglev** is 70-80% of BOM at low volume
2. **Custom maglev design** recommended at >500 units
3. **Injection molding** breaks even at ~100 units
4. **FCC/CE certification** budget: $15-30K

See: `HARDWARE_BOM.md` for detailed component specifications.

---

## Appendix A: Consistency with kagami-hub

| Pattern | kagami-hub | kagami-orb | Status |
|---------|------------|------------|--------|
| Error taxonomy | thiserror | thiserror | ✅ Consistent |
| SafetyResult | Full struct | Full struct | ✅ Consistent |
| Circuit breaker | Full impl | Full impl | ✅ Consistent |
| OrbConfig | TOML-based | TOML-based | ✅ Consistent |
| Async runtime | Tokio | Tokio | ✅ Consistent |
| Logging | tracing | tracing | ✅ Consistent |

## Appendix B: File Structure

```
firmware/orb/
├── Cargo.toml
├── src/
│   ├── lib.rs          # Library exports
│   ├── main.rs         # Entry point
│   ├── api/mod.rs      # WebSocket client
│   ├── error.rs        # Error taxonomy
│   ├── hal/mod.rs      # Hardware abstraction
│   ├── led/mod.rs      # LED animations
│   ├── power/mod.rs    # Battery management
│   ├── safety.rs       # h(x) verification
│   ├── sensors/mod.rs  # Temperature, hall
│   ├── state/
│   │   ├── mod.rs      # State machine
│   │   └── transitions.rs
│   ├── util/mod.rs     # Config, timing
│   └── voice/mod.rs    # Audio pipeline
└── tests/              # Integration tests
```

---

*h(x) ≥ 0 always. The orb will halt if safety constraints are violated.*
