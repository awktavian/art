# Kagami Orb - Wireless HID & Capability Growth System

**Version:** 1.0
**Date:** January 2026
**Status:** SPECIFICATION
**CANONICAL REFERENCE:** See `hardware/SPECS.md` for hardware specifications

---

## Overview

The Kagami Orb can function as a wireless Bluetooth HID (Human Interface Device), enabling keyboard, mouse, and gamepad functionality. Unlike tools designed primarily for security research (Flipper Zero) or passive WiFi monitoring (Pwnagotchi), the Kagami Orb is a household assistant that includes HID capabilities for legitimate automation, accessibility, and convenience use cases.

**Philosophy:** The constraint IS the value. h(x) >= 0 means we build trust, not break it.

---

## Hardware Capabilities

### Bluetooth HID (Primary)

| Component | Capability | Notes |
|-----------|------------|-------|
| **QCS6490** | Bluetooth 5.2 | Main SoC, high-level control |
| **ESP32-S3** | Bluetooth 5.0 LE | Co-processor, HID profile implementation |

The ESP32-S3 handles the Bluetooth HID stack directly, allowing:
- Keyboard HID profile
- Mouse HID profile
- Consumer Control HID profile (media keys, volume)
- Gamepad HID profile
- Custom HID reports

### USB HID (Via Dock)

When docked, the ESP32-S3's USB-OTG capability enables wired HID:
- USB HID Keyboard/Mouse
- USB Mass Storage (for payload transfer)
- USB CDC (serial debugging)

### Comparison to Flipper Zero

| Feature | Flipper Zero | Kagami Orb | Notes |
|---------|--------------|------------|-------|
| **Bluetooth HID** | Yes | Yes | Both support keyboard/mouse |
| **USB HID (BadUSB)** | Yes | Yes (docked) | Orb requires dock connection |
| **Sub-GHz Radio** | Yes (300-928 MHz) | No | Not included - illegal uses |
| **RFID/NFC** | Yes (125kHz, 13.56MHz) | No | Not included |
| **IR Blaster** | Yes | No | Could add via GPIO |
| **GPIO Expansion** | Yes (18 pins) | Limited | Orb is sealed sphere |
| **WiFi** | Yes (ESP32) | Yes (WiFi 6E) | Orb has superior WiFi |
| **AI Processing** | No | Yes (52 TOPS) | Orb can learn patterns |
| **Voice Control** | No | Yes | Orb has 4-mic array |
| **Display** | 128x64 mono | 454x454 AMOLED | Orb has living eye |

**Key Differentiator:** Flipper is a pentester's toolkit. Kagami Orb is an AI assistant that can do some automation tasks. The Orb defaults to helpful, not exploitative.

---

## HID Profiles

### Keyboard Profile

```c
// ESP32-S3 BLE HID Keyboard Report
typedef struct {
    uint8_t modifier;    // Ctrl, Shift, Alt, GUI
    uint8_t reserved;
    uint8_t keycode[6];  // Up to 6 simultaneous keys
} keyboard_report_t;
```

**Supported Features:**
- All standard USB HID keycodes
- Modifier keys (Ctrl, Shift, Alt, Win/Cmd)
- Media keys (play, pause, volume)
- System keys (sleep, wake)

### Mouse Profile

```c
// ESP32-S3 BLE HID Mouse Report
typedef struct {
    uint8_t buttons;     // Left, Right, Middle, Back, Forward
    int8_t x;            // X movement (-127 to 127)
    int8_t y;            // Y movement (-127 to 127)
    int8_t wheel;        // Scroll wheel
    int8_t pan;          // Horizontal scroll
} mouse_report_t;
```

**Spatial Mouse Mode:**
Using the ICM-45686 IMU, the Orb can map physical movement to mouse cursor:
- Tilt forward/back = Y axis
- Tilt left/right = X axis
- Rotation = scroll wheel
- Tap gesture = click

### Consumer Control Profile

Media and system control keys:
- Play/Pause, Stop, Next, Previous
- Volume Up/Down/Mute
- Brightness Up/Down
- Screen Lock
- Calculator, Browser, Email launch

### Gamepad Profile

```c
// ESP32-S3 BLE HID Gamepad Report
typedef struct {
    int16_t x;           // Left stick X
    int16_t y;           // Left stick Y
    int16_t z;           // Right stick X
    int16_t rz;          // Right stick Y
    uint8_t hat;         // D-pad (0-8)
    uint16_t buttons;    // 16 buttons
} gamepad_report_t;
```

The Orb's IMU enables spatial gaming - use the sphere as a motion controller.

---

## DuckyScript Support

[DuckyScript](https://docs.hak5.org/hak5-usb-rubber-ducky/duckyscript-tm-quick-reference) is the standard payload scripting language for HID injection. The Kagami Orb supports a safe subset.

### Supported Commands

| Command | Description | Example |
|---------|-------------|---------|
| `REM` | Comment | `REM This is a comment` |
| `DELAY` | Pause (ms) | `DELAY 500` |
| `STRING` | Type text | `STRING Hello World` |
| `ENTER` | Press Enter | `ENTER` |
| `TAB` | Press Tab | `TAB` |
| `GUI` | Windows/Cmd key | `GUI r` (Run dialog) |
| `CTRL` | Control key | `CTRL c` (Copy) |
| `ALT` | Alt key | `ALT F4` (Close window) |
| `SHIFT` | Shift key | `SHIFT TAB` |
| `CAPSLOCK` | Caps Lock | `CAPSLOCK` |
| `ESCAPE` | Escape key | `ESCAPE` |
| `ARROW` | Arrow keys | `DOWNARROW`, `UPARROW` |

### Safety Restrictions

**NOT SUPPORTED (h(x) >= 0):**
- `EXFIL` commands (data extraction)
- Network commands (curl, wget in payloads)
- Credential harvesting patterns
- Rapid keystroke injection (rate limited)
- Hidden execution (always visual indicator)

### Example Payloads (Safe)

**Presentation Mode:**
```ducky
REM Advance PowerPoint slide
DELAY 100
RIGHTARROW
```

**Open Calculator:**
```ducky
REM Open calculator on Windows
GUI r
DELAY 200
STRING calc
ENTER
```

**Lock Screen:**
```ducky
REM Lock Windows workstation
GUI l
```

**Type Clipboard Content:**
```ducky
REM Paste from clipboard
CTRL v
```

### Payload Library

Built-in payloads are Ed25519 signed and stored in:
```
/kagami/payloads/
├── builtin/           # Factory payloads (signed by Kagami)
│   ├── presentation.duck
│   ├── calculator.duck
│   └── lock_screen.duck
├── user/              # User-created payloads
└── community/         # Community payloads (require trust)
```

---

## Security Framework

### Consent Requirements

| Action | Consent Level | Indicator |
|--------|---------------|-----------|
| BT HID Pairing | Standard BT pairing dialog | Blue LED pulse |
| Payload execution | User voice command or app button | Red LED pulse |
| Recording macro | Explicit start/stop command | Yellow LED pulse |
| USB HID connection | Physical dock connection | Green LED solid |

**No silent or covert HID injection.** The target device always shows a pairing dialog, and the Orb always shows a visual indicator.

### Payload Signing

```rust
// Payload verification
pub struct SignedPayload {
    pub payload: Vec<u8>,
    pub signature: Ed25519Signature,
    pub signer: Ed25519PublicKey,
    pub trust_level: TrustLevel,
}

pub enum TrustLevel {
    Builtin,    // Factory signed, always trusted
    User,       // User's own payloads
    Community,  // Requires explicit trust grant
    Untrusted,  // Will not execute
}
```

All payloads must be signed:
- **Builtin:** Signed by Kagami's factory key
- **User:** Signed by user's device key
- **Community:** Signed by community member's key (requires trust)

### Rate Limiting

```rust
pub struct HidRateLimiter {
    max_keystrokes_per_second: u32,    // Default: 50
    max_mouse_reports_per_second: u32, // Default: 125
    payload_cooldown_ms: u32,          // Default: 1000
    max_payloads_per_minute: u32,      // Default: 10
}
```

Prevents:
- Keystroke flooding
- Denial of service via HID spam
- Rapid-fire payload execution

### Audit Logging

Every HID action is logged locally:

```json
{
    "timestamp": "2026-01-11T12:34:56Z",
    "action": "keyboard_report",
    "target_device": "Tim's MacBook Pro",
    "payload_id": "builtin/presentation.duck",
    "keystrokes": ["RIGHTARROW"],
    "user_initiated": true,
    "consent_method": "voice_command"
}
```

Logs are:
- Stored locally (not cloud)
- Retained for 30 days
- Accessible via companion app
- Exportable for security audit

---

## Capability Growth System

### Philosophy: Always Getting More Capable

Kagami and Kagami Orb should continuously improve through:
1. **Plugin System** - Add new capabilities
2. **AI Learning** - Learn from usage patterns
3. **Mesh Sharing** - Share capabilities between devices
4. **OTA Updates** - Receive new features automatically

### Plugin Architecture

```
/kagami/plugins/
├── builtin/           # Factory plugins
│   ├── hid_keyboard/
│   ├── hid_mouse/
│   └── presentation_mode/
├── community/         # Community plugins
│   └── spatial_mouse/
└── user/              # User plugins
    └── custom_macro/
```

**Plugin Manifest:**
```yaml
# plugin.yaml
name: spatial_mouse
version: 1.0.0
author: kagami-community
description: Use Orb as spatial mouse controller
permissions:
  - imu_access
  - hid_mouse
  - settings_write
entry_point: spatial_mouse.wasm
signature: <ed25519_signature>
```

**Sandboxed Execution:**
Plugins run in WebAssembly (WASM) sandbox:
- No direct hardware access
- API calls through permission system
- Resource limits enforced
- Can be terminated if misbehaving

### AI Learning

The Kagami Orb learns from usage patterns:

**Pattern Recognition:**
```python
# Example: Learn that user always opens Slack at 9am
patterns = [
    {
        "trigger": {"time": "09:00", "day": "weekday"},
        "action": "open_slack",
        "confidence": 0.85,
        "occurrences": 23
    }
]
```

**Suggested Automations:**
When confidence exceeds threshold, Kagami suggests:
> "I noticed you open Slack every weekday at 9am. Want me to do that automatically?"

**Learning Categories:**
- Time-based patterns (daily routines)
- Context-based patterns (when at desk, when in meeting)
- Sequence patterns (after X, usually Y)
- Voice command patterns (common phrasings)

### Mesh Capability Sharing

Multiple Kagami devices can share capabilities:

```
┌─────────────────┐       ┌─────────────────┐
│  Kagami Orb     │◄─────►│  Kagami Hub     │
│  (Living Room)  │ Mesh  │  (Office)       │
└────────┬────────┘       └────────┬────────┘
         │                         │
         │      ┌─────────────┐   │
         └─────►│ Capability  │◄──┘
                │   Registry  │
                └─────────────┘
```

**Capability Registry:**
- Tracks which device has which capabilities
- Routes requests to capable device
- Syncs learned patterns across devices
- Shares plugins (with permission)

**Example:**
> Orb in living room doesn't have IR blaster, but Hub does.
> "Hey Kagami, turn on the TV" → Routes to Hub via mesh.

### OTA Updates

Secure over-the-air updates:

```rust
pub struct OTAUpdate {
    pub version: SemanticVersion,
    pub target: UpdateTarget,  // Firmware, Plugin, Model
    pub payload: Vec<u8>,
    pub signature: Ed25519Signature,
    pub rollback_version: SemanticVersion,
}
```

**Update Channels:**
- **Stable:** Thoroughly tested, recommended
- **Beta:** New features, may have bugs
- **Developer:** Bleeding edge, for testing

**Rollback:**
Every update stores rollback image. If device doesn't boot:
1. Boot into recovery
2. Restore previous version
3. Report failure to Kagami cloud

### Community Capability Marketplace

A curated marketplace for capabilities:

**Categories:**
- **Automation** - Smart home, workflows
- **Accessibility** - Voice control, HID assistance
- **Productivity** - Presentation, macros
- **Entertainment** - Games, media control
- **Developer** - Debugging, testing tools

**Trust Levels:**
| Level | Requirements | Review Process |
|-------|--------------|----------------|
| Verified | Kagami team review | Full code audit |
| Community | 10+ installs, 4+ stars | Automated + community |
| New | Just published | Automated scan only |

---

## Ethical Guidelines

### What Kagami Orb DOES (h(x) >= 0)

- Wireless presentation control
- Accessibility assistance (voice to keystrokes)
- Legitimate automation (macros, workflows)
- Multi-device KVM switching
- Spatial mouse/gamepad for gaming
- Educational security research (with consent)

### What Kagami Orb DOES NOT DO

- WiFi deauthentication attacks
- RFID/NFC cloning without consent
- Covert keystroke injection
- Credential harvesting
- Sub-GHz replay attacks
- Any action without visual/audio indicator

### Developer Mode

For legitimate security research (CTF, pentesting with authorization):

**Unlock Requirements:**
1. Enable Developer Mode in settings
2. Accept explicit warning about capabilities
3. Provide context (CTF, authorized pentest, research)
4. Agree to audit logging

**Additional Capabilities:**
- Raw HID reports
- Custom payload creation
- Extended timing controls
- Detailed protocol logging

**Still Prohibited:**
- WiFi attacks (no hardware)
- RFID/NFC attacks (no hardware)
- Sub-GHz attacks (no hardware)
- Actions without indicator

---

## Implementation Roadmap

### Phase 1: Foundation (Firmware 1.1)
- [ ] ESP32-S3 BLE HID profile implementation
- [ ] Basic keyboard/mouse HID reports
- [ ] LED ring visual indicators for HID mode
- [ ] Settings toggle in companion app
- [ ] Pairing flow with consent

### Phase 2: Enhanced HID (Firmware 1.2)
- [ ] DuckyScript interpreter (safe subset)
- [ ] Payload library (builtin payloads)
- [ ] Macro recording from gesture
- [ ] IMU-to-mouse mapping (spatial control)
- [ ] Consumer control profile

### Phase 3: Plugin System (Firmware 2.0)
- [ ] Plugin loader architecture
- [ ] Capability manifest format
- [ ] WASM sandbox execution
- [ ] Plugin settings UI
- [ ] Community plugin support

### Phase 4: AI Growth (Firmware 2.x)
- [ ] Pattern learning from usage
- [ ] Suggested automations
- [ ] Capability recommendations
- [ ] Mesh capability sharing
- [ ] OTA capability updates

---

## API Reference

### ESP32-S3 HID API

```c
// Initialize HID profiles
esp_err_t kagami_hid_init(void);

// Keyboard
esp_err_t kagami_hid_keyboard_press(uint8_t modifier, uint8_t keycode);
esp_err_t kagami_hid_keyboard_release(void);
esp_err_t kagami_hid_keyboard_type(const char* text);

// Mouse
esp_err_t kagami_hid_mouse_move(int8_t x, int8_t y);
esp_err_t kagami_hid_mouse_click(uint8_t buttons);
esp_err_t kagami_hid_mouse_scroll(int8_t wheel);

// Consumer Control
esp_err_t kagami_hid_consumer_press(uint16_t usage_code);

// Gamepad
esp_err_t kagami_hid_gamepad_report(gamepad_report_t* report);

// DuckyScript
esp_err_t kagami_ducky_execute(const char* script);
esp_err_t kagami_ducky_execute_file(const char* path);
```

### Plugin API

```rust
// Plugin capability interface
pub trait KagamiPlugin {
    fn manifest(&self) -> PluginManifest;
    fn initialize(&mut self, context: PluginContext) -> Result<()>;
    fn execute(&mut self, command: Command) -> Result<Response>;
    fn shutdown(&mut self) -> Result<()>;
}

// Available APIs for plugins
pub trait PluginContext {
    fn hid_keyboard(&self) -> Option<&dyn HidKeyboard>;
    fn hid_mouse(&self) -> Option<&dyn HidMouse>;
    fn imu(&self) -> Option<&dyn ImuSensor>;
    fn led_ring(&self) -> Option<&dyn LedRing>;
    fn storage(&self) -> Option<&dyn PluginStorage>;
    fn settings(&self) -> Option<&dyn PluginSettings>;
}
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial specification |

---

**Document Status:** SPECIFICATION
**Next Action:** Firmware implementation Phase 1
**Author:** Kagami (mirror)
