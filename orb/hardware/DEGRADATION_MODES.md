# Kagami Orb — Graceful Degradation Modes

## Philosophy

When components fail or resources are limited, the Orb should degrade gracefully — reducing capability while maintaining safety and user awareness. The user should always know what's happening.

---

## Degradation Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         DEGRADATION LEVELS                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

LEVEL 0: FULL CAPABILITY
─────────────────────────
• All systems nominal
• Full voice interaction
• Complete smart home control
• Normal LED animations
• Standard power consumption


LEVEL 1: REDUCED PERFORMANCE
─────────────────────────
Triggers: CPU thermal warning, high load
Actions:
  • Reduce LED brightness 50%
  • Throttle CPU to 1.0 GHz
  • Disable non-essential animations
  • Voice still functional
User indication: Slight LED dimming


LEVEL 2: POWER CONSERVATION
─────────────────────────
Triggers: Battery < 30%, Undocked
Actions:
  • LED constellation mode (7 LEDs only)
  • CPU at 600 MHz
  • Reduce wake word sensitivity
  • Disable AI accelerator
  • Shorten response timeouts
User indication: Dim LEDs, amber battery indicator


LEVEL 3: MINIMAL OPERATION
─────────────────────────
Triggers: Battery < 15%, WiFi loss, API timeout
Actions:
  • Single LED heartbeat
  • Wake word only (no full commands)
  • Cache critical commands locally
  • Prioritize reconnection
User indication: Slow amber pulse, voice explains status


LEVEL 4: EMERGENCY MODE
─────────────────────────
Triggers: Battery < 5%, Thermal critical, h(x) approaching 0
Actions:
  • Red LED indicator
  • Voice: "I need to rest soon"
  • Shutdown countdown begins
  • Save state to flash
User indication: Red pulse, countdown voice


LEVEL 5: SAFE SHUTDOWN
─────────────────────────
Triggers: Battery critical, Thermal shutdown, h(x) = 0
Actions:
  • Graceful shutdown sequence
  • State saved
  • Single red flash
  • Power off
User indication: Final red flash, silence
```

---

## Component-Specific Degradation

### WiFi Failure

```
STATE: WiFi disconnected for > 30 seconds

IMMEDIATE:
  • LED: Slow blue pulse (offline indicator)
  • Voice: "I've lost my connection. Trying to reconnect."
  • Begin reconnect attempts (exponential backoff)

AFTER 2 MINUTES:
  • LED: Amber pulse added to blue
  • Voice: "Still offline. Limited functionality available."
  • Enable local-only mode:
    - Wake word detection works
    - LED patterns work
    - Smart home commands cached (max 5)
    - Voice responses limited to status

AFTER 10 MINUTES:
  • LED: Dim amber only
  • Voice: "I'm still offline. Place me on a base or move closer to WiFi."
  • Reduce power consumption
  • Continue reconnect attempts every 30 seconds

ON RECONNECTION:
  • LED: Green flash
  • Voice: "I'm back online."
  • Replay cached commands
  • Sync state with API
```

### API Unreachable

```
STATE: WiFi connected but API not responding

IMMEDIATE:
  • LED: Purple pulse (processing indicator stays)
  • Internal timeout tracking

AFTER 10 SECONDS:
  • LED: Slow purple pulse
  • Voice: "I'm having trouble reaching home. Give me a moment."

AFTER 30 SECONDS:
  • LED: Amber pulse
  • Voice: "Kagami's main system isn't responding. I can still listen."
  • Enable limited local mode

CAPABILITIES WHILE API DOWN:
  • Wake word: YES
  • Voice capture: NO (nowhere to send)
  • LED control: YES (local patterns)
  • Status queries: Limited (cached data)
  • Smart home: NO
  • Time/date: YES (local clock)
```

### Battery Degradation

```
100% - 30%: NORMAL
─────────────────────────
• Full functionality
• No user indication
• Standard power management

30% - 20%: LOW BATTERY
─────────────────────────
• LED: Occasional amber pulse (every 60s)
• Voice (once): "Battery is getting low."
• Reduce LED brightness to 70%
• Disable idle animations

20% - 10%: BATTERY WARNING
─────────────────────────
• LED: Amber pulse every 30s
• Voice (every 5 min): "Battery low. Please place me on a base."
• Reduce LED brightness to 40%
• Disable voice response audio (use LED only)
• Reduce CPU to 600 MHz

10% - 5%: CRITICAL BATTERY
─────────────────────────
• LED: Continuous slow amber
• Voice: "Battery critical. Shutting down in 5 minutes unless docked."
• Disable wake word (save power)
• Only respond to direct dock event

< 5%: IMMINENT SHUTDOWN
─────────────────────────
• LED: Red slow pulse
• Voice: "Goodbye for now."
• Graceful shutdown
• Save state
```

### Thermal Degradation

```
< 60°C: NORMAL
─────────────────────────
• Full performance
• No indication

60°C - 70°C: WARM
─────────────────────────
• Reduce CPU to 1.2 GHz
• Reduce LED brightness 20%
• No user indication (transparent)

70°C - 75°C: HOT
─────────────────────────
• LED: Slight orange tint to all colors
• Reduce CPU to 800 MHz
• Disable AI accelerator (use CPU fallback)
• Voice (once): "I'm running a bit warm."

75°C - 80°C: CRITICAL
─────────────────────────
• LED: Amber overlay on all patterns
• Voice: "I need to cool down. Reducing activity."
• CPU at minimum (600 MHz)
• LEDs at 20%
• Disable voice capture

> 80°C: EMERGENCY
─────────────────────────
• LED: Red pulse
• Voice: "Too hot. Shutting down for safety."
• Graceful shutdown
• Will not restart until < 50°C
```

### Audio System Failure

```
MICROPHONE FAILURE (1-2 mics)
─────────────────────────
• Automatic fallback to remaining mics
• Reduced beamforming quality
• Voice: (none - user won't notice)
• Log error for diagnostics

MICROPHONE FAILURE (3+ mics)
─────────────────────────
• LED: Blue pulse without voice response
• Cannot capture voice
• Visual-only interaction mode
• Log critical error

SPEAKER FAILURE
─────────────────────────
• LED: Enhanced visual feedback
• No audio output
• LED patterns communicate status:
  - Green pulse = success
  - Amber pulse = warning
  - Red pulse = error
• Continue voice capture normally
```

### LED System Failure

```
1-3 LEDs DEAD
─────────────────────────
• Automatic pattern compensation
• Skip dead LEDs in animations
• No user indication
• Log for maintenance

4+ LEDs DEAD
─────────────────────────
• Simplified patterns (static colors)
• Voice: "My display isn't working fully."
• Audio feedback enhanced

COMPLETE LED FAILURE
─────────────────────────
• Audio-only operation
• Voice confirms all actions
• "I can't show you, but I heard that."
• Prioritize reconnection for remote diagnostics
```

### Levitation Failure

```
OSCILLATION DETECTED
─────────────────────────
• Base adjusts PID parameters
• If persistent: controlled descent
• Voice: "Adjusting my balance."

MAGLEV POWER LOSS
─────────────────────────
• Passive magnetic catch engages
• Orb settles gently (< 5mm drop)
• Voice: "I've landed safely."
• Continue operating on base surface

QI POWER LOSS (while docked)
─────────────────────────
• Switch to battery immediately
• Amber battery indicator
• Voice: "Charging stopped. Running on battery."
• Check base alignment
```

---

## State Recovery

### After Power Restoration

```
BOOT SEQUENCE AFTER UNEXPECTED SHUTDOWN
─────────────────────────

1. Hardware initialization (5s)
2. Load saved state from flash
3. Check battery status
4. Attempt WiFi connection

IF STATE WAS SAVED:
  • Voice: "I'm back. I remember where we were."
  • Resume previous activity
  • Replay any cached commands

IF STATE WAS NOT SAVED:
  • Voice: "Hello again. I had an unexpected restart."
  • Default to idle state
  • Request state sync from API
```

### After Thermal Shutdown

```
THERMAL RECOVERY
─────────────────────────

1. Wait until temp < 50°C
2. Boot with reduced power mode
3. Gradually increase capability as temp stable

Voice: "I've cooled down. Starting carefully."

Initial limits:
  • CPU: 800 MHz
  • LEDs: 50%
  • Hailo-10H: disabled

After 5 minutes stable < 60°C:
  • Full capability restored
  • Voice: "All systems normal."
```

---

## User Communication

### Voice Messages (Degradation)

| Trigger | Message |
|---------|---------|
| WiFi loss | "I've lost my connection." |
| API timeout | "I'm having trouble reaching home." |
| Battery 30% | "Battery is getting low." |
| Battery 10% | "Please place me on a base soon." |
| Battery 5% | "Goodbye for now." |
| Thermal 70°C | "I'm running a bit warm." |
| Thermal 80°C | "Too hot. Shutting down for safety." |
| Reconnected | "I'm back online." |
| Recovered | "All systems normal." |

### LED Patterns (Degradation)

| State | Pattern |
|-------|---------|
| Offline | Slow blue pulse |
| API timeout | Slow purple pulse |
| Battery low | Amber pulse every 60s |
| Battery critical | Continuous amber |
| Thermal warning | Orange tint overlay |
| Thermal critical | Amber overlay |
| Emergency | Red pulse |
| Recovered | Green flash |

---

## Logging and Diagnostics

All degradation events are logged:

```json
{
  "timestamp": "2026-01-05T12:00:00Z",
  "event": "degradation_level_change",
  "previous_level": 0,
  "new_level": 2,
  "triggers": [
    {"type": "battery", "value": 28, "threshold": 30}
  ],
  "actions_taken": [
    "reduce_led_brightness",
    "reduce_cpu_frequency"
  ]
}
```

Logs are:
- Stored locally (last 1000 events)
- Synced to API when connected
- Available for diagnostics

---

```
h(x) ≥ 0. Always.

Graceful degradation IS safety.
The orb never surprises.
It explains. It adapts. It survives.

鏡
```
