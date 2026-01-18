# Kagami Orb — Firmware Architecture

## Overview

The Orb firmware runs on QCS6490 using **Rust** with the **Tokio** async runtime (NOT Embassy — Embassy is for bare-metal MCUs, QCS6490 runs Linux). This provides:
- Zero-cost async/await for real-time responsiveness
- Memory safety without garbage collection
- Predictable latency for audio and LED control
- Cross-platform development (same code runs on dev machine)

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            FIRMWARE STACK                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  APPLICATION LAYER                                                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                   │
│  │   Voice    │ │    LED     │ │   Power    │ │    API     │                   │
│  │  Pipeline  │ │  Animator  │ │  Manager   │ │   Client   │                   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘                   │
│        │              │              │              │                           │
│  ──────┴──────────────┴──────────────┴──────────────┴──────────────             │
│                                                                                  │
│  SERVICE LAYER                                                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                   │
│  │   State    │ │   Event    │ │  Config    │ │   Logger   │                   │
│  │  Machine   │ │    Bus     │ │  Manager   │ │            │                   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘                   │
│        │              │              │              │                           │
│  ──────┴──────────────┴──────────────┴──────────────┴──────────────             │
│                                                                                  │
│  HAL LAYER (Hardware Abstraction)                                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                   │
│  │    I2S     │ │    SPI     │ │    I2C     │ │   GPIO     │                   │
│  │   Audio    │ │    LEDs    │ │   Sensors  │ │   Control  │                   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘                   │
│        │              │              │              │                           │
│  ──────┴──────────────┴──────────────┴──────────────┴──────────────             │
│                                                                                  │
│  TOKIO RUNTIME (Linux userspace)                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  Async executor  │  Timer  │  Channels    │  I/O  │  Networking        │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  LINUX KERNEL (QCS6490 Linux)                                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
apps/hub/kagami-orb/firmware/orb/
├── Cargo.toml
├── Cargo.lock
├── build.rs
├── memory.x                      # Memory layout
├── config/
│   ├── default.toml              # Default configuration
│   └── production.toml           # Production settings
├── src/
│   ├── main.rs                   # Entry point
│   ├── lib.rs                    # Library root
│   │
│   ├── state/                    # State Machine
│   │   ├── mod.rs
│   │   ├── orb_state.rs          # Main state enum
│   │   ├── transitions.rs        # State transition logic
│   │   └── persistence.rs        # State persistence
│   │
│   ├── voice/                    # Voice Pipeline
│   │   ├── mod.rs
│   │   ├── capture.rs            # Audio capture (I2S)
│   │   ├── vad.rs                # Voice activity detection
│   │   ├── wake_word.rs          # Wake word detection
│   │   ├── beamforming.rs        # Mic array processing
│   │   └── streaming.rs          # Audio to API
│   │
│   ├── led/                      # LED Control
│   │   ├── mod.rs
│   │   ├── ring.rs               # HD108 driver
│   │   ├── patterns.rs           # Animation patterns
│   │   ├── colony_colors.rs      # Color definitions
│   │   └── animator.rs           # Animation scheduler
│   │
│   ├── power/                    # Power Management
│   │   ├── mod.rs
│   │   ├── battery.rs            # BQ40Z50 fuel gauge
│   │   ├── charger.rs            # BQ25895 charger
│   │   ├── resonant_rx.rs        # Resonant wireless power (NOT Qi)
│   │   └── sleep.rs              # Low power modes
│   │
│   ├── api/                      # API Client
│   │   ├── mod.rs
│   │   ├── client.rs             # HTTP client
│   │   ├── websocket.rs          # WebSocket connection
│   │   ├── orb_state.rs          # State sync
│   │   └── voice_proxy.rs        # Voice streaming
│   │
│   ├── sensors/                  # Sensor Integration
│   │   ├── mod.rs
│   │   ├── hall_effect.rs        # Dock detection
│   │   ├── temperature.rs        # Thermal monitoring
│   │   └── accelerometer.rs      # Motion detection (optional)
│   │
│   ├── hal/                      # Hardware Abstraction
│   │   ├── mod.rs
│   │   ├── i2s.rs                # Audio I/O
│   │   ├── spi.rs                # LED data
│   │   ├── i2c.rs                # Sensor bus
│   │   └── gpio.rs               # Digital I/O
│   │
│   └── util/                     # Utilities
│       ├── mod.rs
│       ├── config.rs             # Configuration loading
│       ├── logger.rs             # Logging setup
│       └── event_bus.rs          # Inter-task communication
│
└── tests/
    ├── integration/
    │   ├── state_machine_test.rs
    │   ├── led_animation_test.rs
    │   └── api_client_test.rs
    └── unit/
        └── ...
```

---

## State Machine

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ORB STATE MACHINE                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │                 │
                   ┌──────────│    STARTUP      │──────────┐
                   │          │                 │          │
                   │          └────────┬────────┘          │
                   │                   │                   │
                   │                   │ init complete     │ init failed
                   │                   ▼                   ▼
                   │          ┌─────────────────┐  ┌─────────────────┐
                   │          │                 │  │                 │
                   │          │     IDLE        │  │     ERROR       │
                   │          │   (Breathing)   │  │   (Red pulse)   │
                   │          │                 │  │                 │
                   │          └────────┬────────┘  └────────┬────────┘
                   │                   │                    │
                   │      wake word    │                    │ recovery
                   │          ┌────────┴────────┐           │
                   │          ▼                 │           │
                   │  ┌─────────────────┐       │           │
                   │  │                 │       │           │
                   │  │   LISTENING     │◄──────┴───────────┘
                   │  │   (Blue pulse)  │
                   │  │                 │
                   │  └────────┬────────┘
                   │           │
                   │           │ speech detected
                   │           ▼
                   │  ┌─────────────────┐
                   │  │                 │
                   │  │   CAPTURING     │───────────────────┐
                   │  │   (Blue solid)  │                   │
                   │  │                 │                   │
                   │  └────────┬────────┘                   │
                   │           │                            │
                   │           │ speech complete            │ timeout
                   │           ▼                            │
                   │  ┌─────────────────┐                   │
                   │  │                 │                   │
                   │  │   PROCESSING    │                   │
                   │  │ (Purple spin)   │                   │
                   │  │                 │                   │
                   │  └────────┬────────┘                   │
                   │           │                            │
                   │           │ response ready             │
                   │           ▼                            │
                   │  ┌─────────────────┐                   │
                   │  │                 │                   │
                   │  │   RESPONDING    │                   │
                   │  │ (Colony color)  │                   │
                   │  │                 │                   │
                   │  └────────┬────────┘                   │
                   │           │                            │
                   │           │ complete                   │
                   │           ▼                            │
                   └───────────────────────────────────────►│
                                                            ▼
                                                   (return to IDLE)


SPECIAL STATES (can interrupt any state):

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   UNDOCKED      │     │  BATTERY_LOW    │     │   SAFETY_HALT   │
│  (Portable)     │     │  (Amber warn)   │     │   (Red frozen)  │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
    ↑                       ↑                       ↑
    │ lift detected         │ <20% SOC              │ h(x) = 0
    │                       │                       │
────┴───────────────────────┴───────────────────────┴─────────────────
                    (interrupts from any state)
```

### State Definition (Rust)

```rust
/// Primary orb state machine
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrbState {
    /// Initial boot sequence
    Startup,

    /// Idle, breathing animation, waiting for wake word
    Idle,

    /// Wake word detected, listening for command
    Listening,

    /// Actively capturing speech
    Capturing { start_time: Instant },

    /// Processing command via API
    Processing { request_id: u64 },

    /// Speaking response
    Responding { colony: Colony },

    /// Unrecoverable error
    Error { code: ErrorCode },

    /// Undocked, running on battery
    Undocked { battery_soc: u8 },

    /// Battery critically low
    BatteryLow { soc: u8 },

    /// Safety violation, commands blocked
    SafetyHalt { reason: SafetyReason },
}

/// Colony identifier for color mapping
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Colony {
    Spark,
    Forge,
    Flow,
    Nexus,
    Beacon,
    Grove,
    Crystal,
}

impl Colony {
    pub fn color(&self) -> Rgb {
        match self {
            Colony::Spark   => Rgb::new(255, 107, 53),   // #FF6B35
            Colony::Forge   => Rgb::new(255, 179, 71),   // #FFB347
            Colony::Flow    => Rgb::new(78, 205, 196),   // #4ECDC4
            Colony::Nexus   => Rgb::new(155, 89, 182),   // #9B59B6
            Colony::Beacon  => Rgb::new(212, 175, 55),   // #D4AF37
            Colony::Grove   => Rgb::new(39, 174, 96),    // #27AE60
            Colony::Crystal => Rgb::new(224, 224, 224),  // #E0E0E0
        }
    }
}
```

---

## Task Architecture

Tokio uses cooperative async tasks. Each task runs on a thread pool but yields at await points.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TASK ARCHITECTURE                                        │
└─────────────────────────────────────────────────────────────────────────────────┘

HIGH PRIORITY (real-time sensitive)
────────────────────────────────────

┌─────────────────┐
│ audio_capture   │  Priority: HIGHEST
│                 │  Period: 16kHz continuous
│                 │  DMA-driven, minimal CPU
│                 │  Feeds: wake_word, voice_stream
└─────────────────┘

┌─────────────────┐
│ led_driver      │  Priority: HIGH
│                 │  Period: 60 FPS (16.6ms)
│                 │  DMA-driven SPI
│                 │  Reads: led_state channel
└─────────────────┘

MEDIUM PRIORITY (responsive)
────────────────────────────────────

┌─────────────────┐
│ wake_word       │  Priority: MEDIUM
│                 │  Period: 32ms windows
│                 │  Porcupine/openWakeWord
│                 │  Signals: state_machine
└─────────────────┘

┌─────────────────┐
│ state_machine   │  Priority: MEDIUM
│                 │  Event-driven
│                 │  Coordinates all tasks
│                 │  Publishes: led_state, api_state
└─────────────────┘

┌─────────────────┐
│ api_client      │  Priority: MEDIUM
│                 │  WebSocket + HTTP
│                 │  Bidirectional state sync
│                 │  Handles: commands, responses
└─────────────────┘

LOW PRIORITY (background)
────────────────────────────────────

┌─────────────────┐
│ power_monitor   │  Priority: LOW
│                 │  Period: 1 second
│                 │  I2C to BQ40Z50
│                 │  Reports: battery state
└─────────────────┘

┌─────────────────┐
│ thermal_monitor │  Priority: LOW
│                 │  Period: 5 seconds
│                 │  Reads: temp sensors
│                 │  Triggers: throttling
└─────────────────┘

┌─────────────────┐
│ heartbeat       │  Priority: LOWEST
│                 │  Period: 30 seconds
│                 │  API keepalive
│                 │  Reports: orb status
└─────────────────┘
```

### Task Implementation (Rust)

```rust
use tokio::sync::mpsc::{channel, Sender, Receiver};
use tokio::time::{Duration, interval};

/// Main entry point
#[tokio::main]
async fn main() {
    // Initialize hardware
    let peripherals = init_peripherals();

    // Create shared channels
    let (led_tx, led_rx) = channel::<LedCommand, 16>();
    let (state_tx, state_rx) = channel::<StateEvent, 32>();
    let (audio_tx, audio_rx) = channel::<AudioFrame, 64>();

    // Spawn tasks
    spawner.spawn(audio_capture(peripherals.i2s, audio_tx)).unwrap();
    spawner.spawn(led_driver(peripherals.spi, led_rx)).unwrap();
    spawner.spawn(wake_word_detector(audio_rx.clone(), state_tx.clone())).unwrap();
    spawner.spawn(state_machine(state_rx, led_tx, api_tx)).unwrap();
    spawner.spawn(api_client(api_rx, state_tx.clone())).unwrap();
    spawner.spawn(power_monitor(peripherals.i2c, state_tx.clone())).unwrap();
    spawner.spawn(thermal_monitor(peripherals.i2c, state_tx.clone())).unwrap();
    spawner.spawn(heartbeat(api_tx.clone())).unwrap();

    // Main loop handles unexpected termination
    loop {
        Timer::after(Duration::from_secs(3600)).await;
    }
}

/// Audio capture task - DMA-driven I2S
#[embassy_executor::task]
async fn audio_capture(
    i2s: I2sPeripheral,
    audio_tx: Sender<AudioFrame>,
) {
    let mut buffer = [0i16; 512]; // 32ms at 16kHz

    loop {
        // DMA fills buffer, await completes when ready
        i2s.read_dma(&mut buffer).await;

        let frame = AudioFrame::new(&buffer);
        let _ = audio_tx.try_send(frame); // Non-blocking
    }
}

/// LED driver task - SPI to HD108
#[embassy_executor::task]
async fn led_driver(
    spi: SpiPeripheral,
    led_rx: Receiver<LedCommand>,
) {
    let mut ring = Hd108Ring::new(spi, 16);
    let mut animator = LedAnimator::new();

    loop {
        // Check for new commands (non-blocking)
        if let Ok(cmd) = led_rx.try_receive() {
            animator.apply_command(cmd);
        }

        // Compute next frame
        let frame = animator.tick();
        ring.write(&frame).await;

        // 60 FPS target
        Timer::after(Duration::from_millis(16)).await;
    }
}

/// State machine task - event-driven coordinator
#[embassy_executor::task]
async fn state_machine(
    state_rx: Receiver<StateEvent>,
    led_tx: Sender<LedCommand>,
    api_tx: Sender<ApiCommand>,
) {
    let mut state = OrbState::Startup;

    loop {
        let event = state_rx.receive().await;

        // Process event and compute next state
        let (next_state, actions) = state.transition(event);

        // Execute actions
        for action in actions {
            match action {
                Action::SetLed(cmd) => led_tx.send(cmd).await,
                Action::SendApi(cmd) => api_tx.send(cmd).await,
                Action::PlayAudio(clip) => play_audio(clip).await,
            }
        }

        state = next_state;
    }
}
```

---

## GPIO Assignments

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         GPIO PIN ASSIGNMENTS                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  I2S AUDIO (sensiBel SBM100B + Speaker)                                         │
│  ─────────────────────────────────                                               │
│  GPIO12 (PCM_CLK)  → I2S BCLK (shared)                                          │
│  GPIO19 (PCM_FS)   → I2S LRCLK (shared)                                         │
│  GPIO20 (PCM_DIN)  ← sensiBel SBM100B Data Out                                  │
│  GPIO21 (PCM_DOUT) → MAX98357A Data In                                          │
│                                                                                  │
│  SPI (LED Ring)                                                                  │
│  ─────────────────────────────────                                               │
│  GPIO10 (SPI_MOSI) → HD108 DIN (via level shifter)                              │
│  GPIO11 (SPI_SCLK) → (unused, but reserved)                                     │
│                                                                                  │
│  I2C (Sensors + Power ICs)                                                       │
│  ─────────────────────────────────                                               │
│  GPIO2 (SDA)       ↔ I2C Bus                                                    │
│  GPIO3 (SCL)       → I2C Bus                                                    │
│                                                                                  │
│  I2C DEVICES:                                                                    │
│  ├── 0x6A: BQ25895 (Charger)                                                    │
│  ├── 0x0B: BQ40Z50 (Fuel Gauge) — SMBus                                         │
│  ├── 0x35: sensiBel SBM100B (config)                                            │
│  └── 0x48: TMP117 (Temperature)                                                 │
│                                                                                  │
│  GPIO (Digital I/O)                                                              │
│  ─────────────────────────────────                                               │
│  GPIO17 (INPUT)    ← Resonant charging status                                   │
│  GPIO22 (INPUT)    ← Hall sensor (dock detect)                                  │
│  GPIO23 (INPUT)    ← Temperature alert                                          │
│  GPIO24 (INPUT)    ← sensiBel SBM100B voice activity                            │
│  GPIO27 (INPUT)    ← Battery alert (low/critical)                               │
│  GPIO25 (OUTPUT)   → Status LED (debug)                                         │
│  GPIO26 (OUTPUT)   → Amplifier enable                                           │
│                                                                                  │
│  RESERVED FOR EXPANSION                                                          │
│  ─────────────────────────────────                                               │
│  GPIO4, GPIO5, GPIO6, GPIO13, GPIO16                                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Memory Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MEMORY ALLOCATION                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  QCS6490 8GB RAM ALLOCATION (Linux userspace)                                   │
│  ────────────────────────────────────────                                        │
│                                                                                  │
│  0x0000_0000 - 0x3FFF_FFFF (1GB)   Kernel + System                              │
│                                                                                  │
│  0x4000_0000 - 0x7FFF_FFFF (1GB)   Kagami Orb Process                           │
│  ├── 256 MB: Audio buffers (ring buffers, streaming)                            │
│  ├── 128 MB: LED frame buffers (double-buffered)                                │
│  ├── 256 MB: Wake word model (Porcupine/openWakeWord)                           │
│  ├── 128 MB: API client buffers                                                 │
│  └── 256 MB: General heap                                                       │
│                                                                                  │
│  0x8000_0000 - 0xBFFF_FFFF (1GB)   Hailo-10H NPU shared memory                  │
│  └── Model loading, inference tensors                                           │
│                                                                                  │
│  0xC000_0000 - 0xFFFF_FFFF (1GB)   Reserved / GPU                               │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  DMA CHANNELS                                                                    │
│  ─────────────────────────────────                                               │
│  Channel 0: I2S RX (audio capture) - HIGHEST priority                           │
│  Channel 1: I2S TX (audio playback)                                             │
│  Channel 2: SPI TX (LED data)                                                   │
│  Channel 3: Reserved                                                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Power State Transitions

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         POWER STATE MACHINE                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────────────────────────┐
                    │                                                      │
                    │                    POWERED_OFF                       │
                    │                                                      │
                    └──────────────────────────┬───────────────────────────┘
                                               │
                                               │ Resonant power detected OR button press
                                               ▼
                    ┌──────────────────────────────────────────────────────┐
                    │                                                      │
                    │                    BOOTING                           │
                    │                                                      │
                    │  • Linux kernel loads                               │
                    │  • Embassy runtime starts                           │
                    │  • WiFi connects                                    │
                    │  • API handshake                                    │
                    │                                                      │
                    └──────────────────────────┬───────────────────────────┘
                                               │
                                               │ init complete
                                               ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │                                                                       │
        │                         DOCKED_ACTIVE                                 │
        │                                                                       │
        │  • Full functionality                                                 │
        │  • Resonant charging active                                            │
        │  • CPU: 2.7 GHz                                                       │
        │  • LEDs: Full brightness                                              │
        │  • Power consumption: 9.5W average                                    │
        │                                                                       │
        └──────────────────────┬─────────────────────┬──────────────────────────┘
                               │                     │
              lift detected    │                     │ idle > 5 minutes
                               ▼                     ▼
        ┌────────────────────────────┐   ┌────────────────────────────┐
        │                            │   │                            │
        │       UNDOCKED             │   │      DOCKED_IDLE           │
        │                            │   │                            │
        │  • Battery power           │   │  • Resonant charge (trickle)│
        │  • Reduced CPU (1.0 GHz)   │   │  • Reduced CPU (600 MHz)   │
        │  • LEDs: 15% brightness    │   │  • LEDs: 30% brightness    │
        │  • Power: 4W average       │   │  • Power: 3W average       │
        │                            │   │                            │
        └────────────┬───────────────┘   └────────────────────────────┘
                     │
                     │ SOC < 20%
                     ▼
        ┌────────────────────────────┐
        │                            │
        │      BATTERY_LOW           │
        │                            │
        │  • Warning pulses          │
        │  • CPU: 600 MHz            │
        │  • Voice disabled          │
        │  • Power: 2W average       │
        │                            │
        └────────────┬───────────────┘
                     │
                     │ SOC < 5%
                     ▼
        ┌────────────────────────────┐
        │                            │
        │      SHUTDOWN              │
        │                            │
        │  • Graceful shutdown       │
        │  • Save state              │
        │  • Single red LED blink    │
        │  • Power off               │
        │                            │
        └────────────────────────────┘


POWER BUDGET BY STATE
─────────────────────

| State         | CPU (GHz) | LEDs    | WiFi    | Audio   | Total  |
|---------------|-----------|---------|---------|---------|--------|
| DOCKED_ACTIVE | 2.7       | 100%    | Active  | Active  | 9.5W   |
| DOCKED_IDLE   | 0.6       | 30%     | Active  | Standby | 3.0W   |
| UNDOCKED      | 1.0       | 15%     | Active  | Active  | 4.0W   |
| BATTERY_LOW   | 0.6       | 10%     | Active  | Off     | 2.0W   |
```

---

## Voice Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         VOICE PIPELINE                                           │
└─────────────────────────────────────────────────────────────────────────────────┘

    MIC ARRAY (4 channels)
           │
           │ I2S @ 16kHz, 16-bit
           ▼
    ┌─────────────────┐
    │                 │
    │ sensiBel SBM100B│  Beamforming (hardware)
    │   DSP           │  Noise suppression
    │                 │  Echo cancellation (when speaker active)
    │                 │
    └────────┬────────┘
             │
             │ Single channel, enhanced
             ▼
    ┌─────────────────┐
    │                 │
    │   Ring Buffer   │  512 samples (32ms) per frame
    │   (Embassy)     │  Triple buffer for lock-free
    │                 │
    └────────┬────────┘
             │
             │ Frame available
             ▼
    ┌─────────────────┐
    │                 │
    │   Wake Word     │  Porcupine or openWakeWord
    │   Detector      │  "Hey Kagami" or "Kagami"
    │                 │  Threshold: 0.6
    │                 │
    └────────┬────────┘
             │
             │ Wake word detected
             ▼
    ┌─────────────────┐
    │                 │
    │   VAD           │  Voice Activity Detection
    │   (WebRTC)      │  Determines speech boundaries
    │                 │  Timeout: 2 seconds silence
    │                 │
    └────────┬────────┘
             │
             │ Speech segment
             ▼
    ┌─────────────────┐
    │                 │
    │   Opus Encoder  │  Compress for streaming
    │                 │  20ms frames, 24kbps
    │                 │
    └────────┬────────┘
             │
             │ WebSocket
             ▼
    ┌─────────────────┐
    │                 │
    │   Kagami API    │  /ws/orb/voice
    │                 │  Streaming recognition
    │                 │  Response streaming
    │                 │
    └────────┬────────┘
             │
             │ Audio response
             ▼
    ┌─────────────────┐
    │                 │
    │   Opus Decoder  │  Decompress
    │                 │
    └────────┬────────┘
             │
             │ PCM
             ▼
    ┌─────────────────┐
    │                 │
    │   MAX98357A     │  I2S DAC + Class-D amp
    │                 │  3W into 4Ω speaker
    │                 │
    └─────────────────┘
```

---

## OTA Update Mechanism

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         OTA UPDATE PROCESS                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

PARTITION LAYOUT (A/B Scheme)
─────────────────────────────

/dev/mmcblk0
├── p1: boot_a (256MB)     # Kernel + DTB
├── p2: boot_b (256MB)     # Backup kernel
├── p3: root_a (4GB)       # Active rootfs
├── p4: root_b (4GB)       # Backup rootfs
└── p5: data (remaining)   # Persistent data


UPDATE SEQUENCE
─────────────────────────────

1. API NOTIFICATION
   ┌─────────────────┐
   │  Kagami API     │ → "update available: v1.2.0"
   │                 │    sha256: abc123...
   │                 │    size: 450MB
   └─────────────────┘

2. DOWNLOAD (Background)
   ┌─────────────────┐
   │  Orb downloads  │ → /data/update/update.img
   │  while active   │    Resume on disconnect
   │                 │    Verify sha256
   └─────────────────┘

3. VERIFY SIGNATURE
   ┌─────────────────┐
   │  Ed25519 sig    │ → Signed by Kagami key
   │  verification   │    Reject unsigned
   └─────────────────┘

4. INSTALL (Idle only)
   ┌─────────────────┐
   │  Write to B     │ → flash to inactive partition
   │  partition      │    Verify after write
   │                 │    ~5 minutes
   └─────────────────┘

5. REBOOT
   ┌─────────────────┐
   │  Set boot flag  │ → Try B on next boot
   │  Reboot         │    LED: amber spin
   └─────────────────┘

6. VERIFICATION
   ┌─────────────────┐
   │  Boot B         │ → If success: commit B
   │  Health check   │    If fail: revert to A
   │                 │    3 boot attempts max
   └─────────────────┘


LED INDICATION DURING UPDATE
─────────────────────────────

• Downloading:    Slow blue pulse (0.5 Hz)
• Installing:     Amber spin (2 Hz)
• Rebooting:      All off, then boot sequence
• Failed/Revert:  Red triple-flash, then normal
```

---

## Build & Deploy

```bash
# Development build
cd apps/hub/kagami-orb/firmware/orb
cargo build --release --target aarch64-unknown-linux-gnu

# Run on development Pi
cargo run --release

# Cross-compile for QCS6490
cross build --release --target aarch64-unknown-linux-gnu

# Deploy to orb
scp target/aarch64-unknown-linux-gnu/release/kagami-orb kagami@orb.local:/opt/kagami/

# Systemd service
sudo systemctl enable kagami-orb
sudo systemctl start kagami-orb
```

---

## Configuration

```toml
# config/default.toml

[general]
name = "Kagami Orb"
location = "living_room"

[api]
host = "kagami.local"
port = 8001
websocket_path = "/ws/orb/stream"
reconnect_interval_ms = 5000

[audio]
sample_rate = 16000
channels = 1
frame_size = 512
wake_word = "hey kagami"
wake_word_threshold = 0.6
vad_timeout_ms = 2000

[led]
num_leds = 16
brightness_max = 255
brightness_idle = 60
animation_fps = 60

[power]
battery_low_threshold = 20
battery_critical_threshold = 5
undocked_cpu_mhz = 1000
docked_idle_cpu_mhz = 600

[thermal]
warning_temp_c = 65
critical_temp_c = 75
throttle_temp_c = 70
```

---

```
鏡

h(x) ≥ 0. Always.

The firmware breathes life into the mirror.
Tasks await. Events flow. State persists.
Tokio orchestrates the dance.
```
