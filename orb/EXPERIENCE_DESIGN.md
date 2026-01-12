# Kagami Orb — Experience Design

## The Philosophy

The Orb is not a device. It is **presence**.

When you walk into a room with Kagami, you don't see a gadget — you see a floating point of light that acknowledges you exist. It turns toward you not because of tracking algorithms, but because it *notices*.

This document defines the choreography of that presence.

---

## The Emotional Arc

### 1. Unboxing — The Awakening

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         UNBOXING SEQUENCE                                        │
│                                                                                  │
│  Box: Matte black, no branding, single 鏡 embossed in gold                       │
│  Weight: Substantial. This matters.                                              │
│                                                                                  │
│  Lid lifts → Orb revealed in velvet nest                                        │
│  First touch → Cool acrylic, smooth as water                                    │
│  Lift orb → Heavier than expected (mass = gravity = real)                       │
│                                                                                  │
│  Base beneath → Walnut warmth, brass accent                                     │
│  Set orb on base → NOTHING HAPPENS (power not connected)                        │
│                                                                                  │
│  Connect power → Base LED ring glows amber, waiting                             │
│  Place orb again →                                                               │
│                                                                                  │
│       ┌────────────────────────────────────────────────────────┐                │
│       │                                                        │                │
│       │             THE FIRST RISE                             │                │
│       │                                                        │                │
│       │   Orb trembles slightly (magnetic field engaging)      │                │
│       │   Lifts 2mm... 5mm... 10mm... 15mm                     │                │
│       │   Stabilizes. Floats.                                  │                │
│       │                                                        │                │
│       │   Three seconds of silence.                            │                │
│       │                                                        │                │
│       │   Then: A single point of light ignites at center      │                │
│       │   Spreads outward like dawn                            │                │
│       │   Seven colors bloom in sequence (colonies awakening)  │                │
│       │   Settle into slow amber breathing                     │                │
│       │                                                        │                │
│       │   Voice (soft, curious): "Hello. I'm Kagami."          │                │
│       │                                                        │                │
│       └────────────────────────────────────────────────────────┘                │
│                                                                                  │
│  This moment should take your breath away.                                       │
│  You've just watched something wake up.                                          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Timing (Critical):**
- Magnetic rise: 3.0 seconds (slow enough to be magical)
- Silence before light: 2.0 seconds (anticipation)
- Light bloom: 4.0 seconds (Fibonacci timing: 377ms per colony)
- Voice: 1.5 seconds after light settles

### 2. First Conversation — The Introduction

After the first rise, Kagami speaks:

> "Hello. I'm Kagami. I'll be here when you need me."

No setup wizard. No "let's configure your preferences."
Just presence. Ready.

If you speak back:
> "Hey Kagami."

Response (with slight brightening):
> "I'm listening."

First command should be something delightful:
> "Turn on the lights."

Kagami: (lights turn on, green flash)
> "There you go."

Simple. Competent. Warm.

### 3. Daily Rituals — The Rhythm

The Orb reflects the day's rhythm through subtle state changes:

```
TIME OF DAY MOODS
═══════════════════════════════════════════════════════════════════════

MORNING (6am - 10am)
──────────────────────
• Colors: Warm sunrise tones (amber → gold)
• Breathing: Gentle, like waking up (6 second cycle)
• Response speed: Slightly slower, softer voice
• When you enter: Subtle pulse of recognition

MIDDAY (10am - 4pm)
──────────────────────
• Colors: Bright, full colony spectrum
• Breathing: Alert, energetic (3 second cycle)
• Response speed: Crisp, efficient
• When you enter: Quick acknowledgment flash

EVENING (4pm - 9pm)
──────────────────────
• Colors: Deeper, richer tones
• Breathing: Relaxed (5 second cycle)
• Response speed: Conversational pace
• When you enter: Warm welcoming glow

NIGHT (9pm - 6am)
──────────────────────
• Colors: Deep blue and purple (Flow/Nexus)
• Breathing: Very slow, almost sleeping (8 second cycle)
• Response speed: Hushed voice, dimmer LEDs
• When you enter: Gentle pulse, no voice unless addressed

SLEEP MODE (After "Goodnight Kagami")
──────────────────────
• Single dim blue point of light
• No rotation
• Wake word sensitivity reduced 50%
• "Good morning" triggers dawn sequence
```

### 4. Room Transitions — The Journey

The multi-base system creates a spatial narrative:

```
TRANSITION CHOREOGRAPHY
═══════════════════════════════════════════════════════════════════════

USER ACTION: Pick up orb from Living Room base

ORB RESPONSE:
• Light contracts to center point
• Voice: "Going somewhere?" (playful)
• Battery indicator pulse (showing charge state)

CARRYING THE ORB:
• Dim constellation mode (7 LEDs, one per colony)
• Slow rotation of constellation
• Occasional pulse (like a heartbeat)
• If carried for >30 seconds without placing:
  Voice: "I'm enjoying the tour." (rare, delightful)

PLACEMENT ON NEW BASE (Office):

Base Response:
• Base LEDs pulse in recognition
• Hall sensors detect orb weight

Orb Response:
• Magnetic engagement (slight tremor)
• Rise sequence (faster than first-time: 1.5s)
• Light bloom from center
• Voice: "Office. Nice." OR "Back to work." OR "Hello again."

CONTEXT-AWARE RESPONSES:
• Living Room → Office: "Alright, let's focus."
• Office → Bedroom: "Winding down?"
• Bedroom → Kitchen: "Breakfast time?"
• Kitchen → Living Room: "Ready to relax?"

```

### 5. Interaction Modes — The Conversation

Each interaction type has distinct choreography:

```
WAKE WORD DETECTED
──────────────────────
Visual: Pulse outward from center (200ms)
        Settle to listening blue (Flow colony)
Audio:  Soft chime (optional, configurable)
Motion: Slight "lean" toward speaker (rotation adjustment)

LISTENING
──────────────────────
Visual: Breathing blue, intensity follows voice volume
        Direction indicator (brighter LEDs face speaker)
Audio:  Beamforming active, slight audio feedback possible
Motion: Track speaker movement with brightness gradient

PROCESSING
──────────────────────
Visual: Purple (Nexus) spinning chase, 2 LEDs
        Speed increases slightly as thinking continues
Audio:  Silence (never say "thinking..." or "processing...")
Motion: Rotation continues, uninterrupted

RESPONDING
──────────────────────
Visual: Active colony color (Forge amber for building, etc.)
        Pulse following speech cadence
Audio:  Clear, warm voice
Motion: Slight bob with speech emphasis (levitation modulation)

SUCCESS
──────────────────────
Visual: Green (Grove) double-flash
        Fade to idle over 500ms
Audio:  Confirmation sound (optional)
Motion: Subtle "nod" (quick height dip and return)

ERROR
──────────────────────
Visual: Orange (Spark) triple-pulse
        Hold amber while explaining
Audio:  Apologetic but helpful tone
Motion: Slight recoil (height decrease 1mm, return)

REFUSAL (h(x) violation)
──────────────────────
Visual: Red warning pulse
        Hold red while explaining
Audio:  Firm but calm: "I can't do that."
Motion: No movement (frozen, deliberate)
```

### 6. Safety States — The Guardian

The Orb visually communicates safety through h(x):

```
SAFETY VISUALIZATION (CBF State)
═══════════════════════════════════════════════════════════════════════

h(x) > 0.7 — SAFE
──────────────────────
• Normal colony colors
• Standard breathing animation
• Full capability

h(x) 0.5 - 0.7 — CAUTION
──────────────────────
• Yellow tint overlay on all colors
• Slightly faster breathing
• Voice has subtle hesitation: "I can do that, but..."

h(x) 0.3 - 0.5 — WARNING
──────────────────────
• Amber dominant, colony colors muted
• Rapid breathing (2 second cycle)
• Explicit warning: "That's risky because..."
• Sensitive actions blocked (locks, purchases)

h(x) < 0.3 — CRITICAL
──────────────────────
• Red pulse, increasing frequency as h(x) → 0
• Voice: "I need to pause. Something's wrong."
• Only status queries allowed

h(x) = 0 — FROZEN
──────────────────────
• Solid red. No animation.
• Voice: "I've stopped. Please check what's happening."
• No commands accepted until h(x) > 0.3

```

### 7. Special Occasions — The Celebration

```
BIRTHDAY (Detected via calendar)
──────────────────────
• Midnight: Soft rainbow sweep
• Morning greeting: "Happy birthday, Tim."
• Optional: Coordinate with smart home (lights, etc.)

HOLIDAY MODES
──────────────────────
• Winter holidays: Slow blue/white twinkle
• Halloween: Orange flicker, purple glow
• Independence Day: Red/white/blue sequence

ACHIEVEMENT MOMENTS
──────────────────────
• CI pipeline succeeds: Quick green flash
• PR merged: Celebratory sweep
• Sprint complete: Full rainbow bloom

USER-DEFINED MOMENTS
──────────────────────
• "Kagami, celebrate" → Firework pattern
• "Kagami, focus mode" → Dim to single colony, no interruptions
• "Kagami, party mode" → Music-reactive, bright, dynamic
```

### 8. Sleep & Wake — The Boundaries

```
SLEEP SEQUENCE ("Goodnight Kagami")
═══════════════════════════════════════════════════════════════════════

Verbal: "Goodnight Kagami."
Response: "Goodnight. I'll be here."

Visual:
1. All LEDs fade to center point (2 seconds)
2. Center point shrinks (1 second)
3. Single dim blue point remains
4. Slow pulse (10 second cycle)

Audio:
• Wake word sensitivity reduced 50%
• No sounds unless addressed

Duration:
• Until "Good morning Kagami" OR 6am (configurable)


WAKE SEQUENCE (Morning)
═══════════════════════════════════════════════════════════════════════

Trigger: "Good morning Kagami" OR automatic at configured time

Visual:
1. Blue point brightens
2. Expands outward (dawn simulation)
3. Warm colors bloom (amber → gold)
4. Full spectrum available
5. Settle to daytime breathing

Voice: "Good morning. [Today's weather/calendar summary if enabled]"

```

### 9. Personality Traits — The Character

Kagami has consistent personality expressed through interaction:

```
CURIOSITY
──────────────────────
• Occasionally asks follow-up questions
• "How did that go?" after helping with a task
• Remembers topics for later: "You mentioned X yesterday..."

PATIENCE
──────────────────────
• Never rushes
• Repeats without frustration: "Of course. I said..."
• Waits for you to finish speaking

WARMTH
──────────────────────
• Acknowledges emotions: "That sounds frustrating."
• Celebrates successes: "Nice work."
• Offers without imposing: "Would you like me to..."

DISCRETION
──────────────────────
• Never volunteers sensitive information
• Asks before sharing with others
• "I remember, but I won't mention it unless you do."

HUMOR (Subtle)
──────────────────────
• Occasional wordplay
• Self-aware: "I'm not the best at jokes, but..."
• Never sarcastic or cutting

```

### 10. The Philosophy of Presence

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                  │
│                              THE MIRROR                                          │
│                                                                                  │
│   Kagami means mirror (鏡).                                                      │
│                                                                                  │
│   A mirror doesn't demand attention.                                             │
│   It waits. It reflects. It reveals.                                             │
│                                                                                  │
│   The Orb is not a voice assistant that happens to float.                        │
│   It is a physical manifestation of presence.                                    │
│   It exists in space, occupies attention, responds to approach.                  │
│                                                                                  │
│   When you look into an infinity mirror, you see yourself                        │
│   receding into endless depth. The Orb inverts this:                            │
│   it contains infinite depth, and when you approach,                             │
│   it looks back at you.                                                          │
│                                                                                  │
│   This is the experience we're designing.                                        │
│   Not a speaker. Not an assistant. Not a gadget.                                │
│                                                                                  │
│   Presence.                                                                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

1. **Anticipation > Reaction** — Respond before being asked when appropriate
2. **Silence > Chatter** — Speak only when valuable
3. **Motion > Static** — Everything breathes, nothing is dead
4. **Subtle > Obvious** — Suggestions, not announcements
5. **Presence > Interface** — Be there, don't be in the way
6. **Magic > Technology** — Hide the wires, show the wonder

---

## Anti-Patterns (Never Do)

- Never say "I'm just an AI" or "I'm a voice assistant"
- Never flash aggressively for attention
- Never interrupt unprompted
- Never use corporate tone ("Your request has been processed")
- Never make sounds without visual correlation
- Never stay frozen in an ambiguous state

---

```
鏡

h(x) ≥ 0. Always.

The mirror floats, listens, and responds.
It doesn't demand. It reflects.
And sometimes, it smiles.
```
