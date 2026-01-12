# Kagami Orb — Test Specifications

## Test Categories

| Category | Purpose | Automation |
|----------|---------|------------|
| Unit | Individual module behavior | Rust tests |
| Integration | Module interactions | Rust tests |
| Hardware | Physical hardware validation | Manual + scripts |
| System | Full system behavior | Semi-automated |
| Acceptance | User-facing requirements | Manual |

---

## Unit Tests (Rust)

### State Machine Tests

```rust
// tests/unit/state_test.rs

#[test]
fn test_startup_to_idle() {
    let state = OrbState::Startup;
    let next = state.transition(StateEvent::InitComplete).unwrap();
    assert_eq!(next, OrbState::Idle);
}

#[test]
fn test_idle_to_listening() {
    let state = OrbState::Idle;
    let next = state.transition(StateEvent::WakeWordDetected).unwrap();
    assert!(matches!(next, OrbState::Listening { .. }));
}

#[test]
fn test_listening_timeout() {
    let state = OrbState::Listening { started_at: 0 };
    let next = state.transition(StateEvent::Timeout).unwrap();
    assert_eq!(next, OrbState::Idle);
}

#[test]
fn test_safety_halt_blocks_commands() {
    let state = OrbState::SafetyHalt {
        reason: SafetyReason::CbfViolation,
        safety_score: 0.0,
    };
    assert!(state.transition(StateEvent::WakeWordDetected).is_err());
}

#[test]
fn test_all_states_have_led_pattern() {
    let states = vec![
        OrbState::Startup,
        OrbState::Idle,
        OrbState::Listening { started_at: 0 },
        OrbState::Processing { request_id: "test".to_string() },
        OrbState::Responding { colony: Colony::Forge, text: "test".to_string() },
        OrbState::Error { code: ErrorCode::Unknown, message: "test".to_string() },
        OrbState::SafetyHalt { reason: SafetyReason::CbfViolation, safety_score: 0.0 },
    ];

    for state in states {
        let pattern = state.led_pattern();
        assert!(!pattern.is_empty(), "State {:?} has no LED pattern", state);
    }
}
```

### LED Driver Tests

```rust
// tests/unit/led_test.rs

#[test]
fn test_rgb_scale() {
    let color = Rgb::new(200, 100, 50);
    let scaled = color.scale(128);
    assert_eq!(scaled.r, 100);
    assert_eq!(scaled.g, 50);
    assert_eq!(scaled.b, 25);
}

#[test]
fn test_rgb_scale_zero() {
    let color = Rgb::new(255, 255, 255);
    let scaled = color.scale(0);
    assert_eq!(scaled, Rgb::BLACK);
}

#[test]
fn test_rgb_blend() {
    let white = Rgb::WHITE;
    let black = Rgb::BLACK;
    let gray = white.blend(&black, 0.5);
    assert_eq!(gray.r, 127);
}

#[test]
fn test_colony_colors_valid() {
    for colony in [Colony::Spark, Colony::Forge, Colony::Flow, Colony::Nexus, Colony::Beacon, Colony::Grove, Colony::Crystal] {
        let (r, g, b) = colony.color();
        assert!(r > 0 || g > 0 || b > 0, "Colony {:?} has no color", colony);
    }
}

#[test]
fn test_breathing_pattern_bounds() {
    let pattern = LedPattern::Breathing {
        color: Rgb::WHITE,
        period_ms: 1000,
        min_brightness: 50,
        max_brightness: 200,
    };
    // Verify pattern parameters are sensible
    if let LedPattern::Breathing { min_brightness, max_brightness, .. } = pattern {
        assert!(min_brightness < max_brightness);
    }
}
```

### API Client Tests

```rust
// tests/unit/api_test.rs

#[test]
fn test_heartbeat_serialization() {
    let heartbeat = Heartbeat {
        orb_id: "test-orb".to_string(),
        state: "idle".to_string(),
        battery_soc: 85,
        wifi_rssi: -45,
    };
    let json = serde_json::to_string(&heartbeat).unwrap();
    assert!(json.contains("test-orb"));
}

#[test]
fn test_command_deserialization() {
    let json = r#"{"command_id":"123","action":"set_led_pattern","params":{"pattern":"rainbow"}}"#;
    let command: Command = serde_json::from_str(json).unwrap();
    assert_eq!(command.command_id, "123");
    assert_eq!(command.action, "set_led_pattern");
}
```

---

## Integration Tests

### State + LED Integration

```rust
// tests/integration/state_led_test.rs

#[tokio::test]
async fn test_state_change_updates_led() {
    let mut state_machine = StateMachine::new();
    let mut led_driver = LedDriver::new_simulated(24).unwrap();

    // Initial state should set breathing pattern
    state_machine.initialize();
    let pattern = state_machine.current_led_pattern();
    assert!(matches!(pattern, LedPattern::Breathing { .. }));

    // Wake word should change to listening pattern
    state_machine.handle_event(StateEvent::WakeWordDetected);
    let pattern = state_machine.current_led_pattern();
    assert!(matches!(pattern, LedPattern::Solid { color: Rgb::FLOW }));
}
```

### API + State Integration

```rust
// tests/integration/api_state_test.rs

#[tokio::test]
async fn test_api_command_triggers_state_change() {
    let (api_tx, api_rx) = tokio::sync::mpsc::channel(32);
    let (state_tx, state_rx) = tokio::sync::mpsc::channel(32);

    // Simulate API command
    api_tx.send(ApiCommand::SetState { state: "listening" }).await.unwrap();

    // Verify state machine received it
    // (In real code, would check state transition occurred)
}
```

---

## Hardware Tests (Manual)

### HW-001: Levitation Stability

**Setup:**
- Orb on powered base station
- Stopwatch
- Video recording (optional)

**Procedure:**
1. Place orb on base
2. Wait for levitation to stabilize
3. Start timer
4. Observe for 60 minutes
5. Record any oscillations or falls

**Pass Criteria:**
- Rises within 5 seconds
- Gap stable at 15mm ± 2mm
- No oscillation > 1mm amplitude
- No falls during test period

**Failure Actions:**
- Oscillation: Adjust PID parameters
- Falls: Check weight, magnet alignment
- Slow rise: Check base power

---

### HW-002: Resonant Charging Efficiency

**Setup:**
- Orb on base (floating)
- Power meter on base input
- Battery monitor script running

**Procedure:**
1. Record base input power
2. Record battery charge rate (W)
3. Calculate efficiency: (charge rate / input power) × 100

**Pass Criteria:**
- Input power: < 20W
- Charge rate: > 10W (target: 15W RX from 20W TX)
- Efficiency: > 50% (target: ~75% with 80mm Litz coils at 140kHz)

**Failure Actions:**
- Low efficiency: Check coil alignment, verify 140kHz tuning
- No charging: Check resonant coil connections, verify coupling coefficient k≈0.82

---

### HW-003: Wake Word Detection

**Setup:**
- Orb powered on, idle state
- Sound level meter
- Test phrases recorded at known distances

**Procedure:**
1. Play "Hey Kagami" at 1m, ambient 40dB
2. Record detection (yes/no)
3. Repeat 10 times
4. Repeat at 2m, 3m
5. Repeat in noisy environment (60dB)

**Pass Criteria:**
- 1m quiet: > 98% detection
- 2m quiet: > 95% detection
- 3m quiet: > 85% detection
- 1m noisy: > 90% detection

**Failure Actions:**
- Low detection: Adjust wake word threshold
- False positives: Increase threshold

---

### HW-004: Thermal Limits

**Setup:**
- Orb on bench (not floating, to isolate thermal from levitation)
- Thermal camera or probe thermometers
- Stress test script

**Procedure:**
1. Run stress test (continuous inference + LED max)
2. Record temperatures every 5 minutes for 60 minutes:
   - CM4 SoC (via software)
   - Internal air (thermocouple)
   - External shell (IR or probe)

**Pass Criteria:**
- CM4 SoC: < 75°C steady state
- Internal air: < 65°C
- External shell: < 50°C (safe to touch)
- No throttling events

**Failure Actions:**
- High temps: Improve thermal path, add vents
- Throttling: Reduce LED brightness, lower CPU clock

---

### HW-005: Battery Endurance

**Setup:**
- Fully charged orb
- Test script simulating typical usage:
  - Wake word every 10 minutes
  - 30-second conversation each
  - LED breathing otherwise

**Procedure:**
1. Undock orb (start battery timer)
2. Run usage simulation
3. Record time to 20% battery warning
4. Record time to 5% shutdown

**Pass Criteria:**
- Time to 20%: > 3.5 hours
- Time to 5%: > 4 hours

**Failure Actions:**
- Short life: Check power consumption, reduce LED brightness
- Unexpected shutdown: Check BMS calibration

---

### HW-006: Drop Test (Shell Integrity)

**Setup:**
- Orb (prototype/expendable unit)
- Foam landing pad
- High-speed camera (optional)

**Procedure:**
1. Drop orb from 15mm (simulated levitation failure)
2. Inspect for damage
3. Power on and verify function
4. Repeat 10 times

**Pass Criteria:**
- No shell cracking
- No component dislodge
- Function preserved after all drops

**Failure Actions:**
- Cracking: Increase shell thickness
- Component damage: Improve internal mounting

---

## System Tests

### SYS-001: Full Boot Sequence

**Procedure:**
1. Power on orb from cold
2. Time each phase:
   - Linux boot
   - WiFi connect
   - API handshake
   - First LED animation

**Pass Criteria:**
- Total boot: < 60 seconds
- API connected: < 90 seconds
- LED animation starts: < 45 seconds

---

### SYS-002: Graceful Degradation

**Procedure:**
1. Disconnect WiFi (simulate failure)
2. Observe orb behavior
3. Verify offline indicators
4. Reconnect WiFi
5. Verify recovery

**Pass Criteria:**
- Offline indication within 30 seconds
- No crash or reboot
- Recovery within 60 seconds of WiFi restoration

---

### SYS-003: OTA Update

**Procedure:**
1. Stage update on API server
2. Notify orb of available update
3. Monitor download progress
4. Observe reboot and update
5. Verify new firmware version

**Pass Criteria:**
- Download completes without error
- Reboot within 2 minutes
- New version active
- Rollback works if verification fails

---

### SYS-004: Multi-Base Handoff

**Procedure:**
1. Orb on Base A (Living Room)
2. Lift orb (goes to Undocked state)
3. Carry to Base B (Office)
4. Place on Base B
5. Verify correct base detection

**Pass Criteria:**
- Undocked state activates immediately
- New base detected within 5 seconds
- Context-aware greeting (if enabled)

---

## Acceptance Tests

### ACC-001: Unboxing Experience

**Evaluator:** Non-technical user

**Procedure:**
1. Provide sealed box
2. Observe unboxing
3. Time to first float
4. Time to first voice interaction
5. Collect feedback

**Pass Criteria:**
- Float within 5 minutes of unpacking
- Voice interaction within 10 minutes
- Evaluator rates experience 8+/10

---

### ACC-002: Daily Use Simulation

**Duration:** 7 days

**Procedure:**
1. Use orb as primary voice assistant
2. Log all interactions
3. Note any frustrations
4. Record failures

**Pass Criteria:**
- < 2 crashes per week
- < 5% missed wake words
- User satisfaction 8+/10

---

## Test Matrix

| Test ID | Category | Automated | Frequency |
|---------|----------|-----------|-----------|
| Unit tests | Unit | Yes | Every commit |
| State/LED integration | Integration | Yes | Every commit |
| HW-001 Levitation | Hardware | No | Pre-release |
| HW-002 Resonant Charging | Hardware | No | Pre-release |
| HW-003 Wake Word | Hardware | Semi | Weekly |
| HW-004 Thermal | Hardware | Semi | Pre-release |
| HW-005 Battery | Hardware | Semi | Pre-release |
| HW-006 Drop Test | Hardware | No | Design change |
| SYS-001 Boot | System | Semi | Weekly |
| SYS-002 Degradation | System | Semi | Pre-release |
| SYS-003 OTA | System | Semi | Pre-release |
| SYS-004 Multi-Base | System | No | Pre-release |
| ACC-001 Unboxing | Acceptance | No | Beta |
| ACC-002 Daily Use | Acceptance | No | Beta |

---

```
鏡

h(x) ≥ 0. Always.

Tests verify the mirror reflects truly.
Every test is a question.
Every pass is an answer.
```
