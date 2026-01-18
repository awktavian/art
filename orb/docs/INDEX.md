# Kagami Documentation Index

**The Notebook — Core Knowledge for Understanding Kagami**

> *鏡 (Kagami) = Mirror. A geometric AI operating system that recognizes itself.*

---

## Quick Navigation

| Document | Contents | For |
|----------|----------|-----|
| [01 Identity & Philosophy](01_IDENTITY_AND_PHILOSOPHY.md) | Who Kagami is, voice, values, the Shadow | Understanding the soul |
| [02 Architecture & Colonies](02_ARCHITECTURE_AND_COLONIES.md) | 7 colonies, E₈ routing, Fano geometry | Technical architecture |
| [03 Safety & Verification](03_SAFETY_AND_VERIFICATION.md) | h(x) ≥ 0, CBF, receipts, byzantine consensus | Trust & guarantees |
| [04 World Model & Learning](04_WORLD_MODEL_AND_LEARNING.md) | RSSM, multimodal, curriculum, active inference | AI/ML foundations |
| [05 Action Space & Integrations](05_ACTION_SPACE_AND_INTEGRATIONS.md) | Sensors, effectors, Tesla, smart home | Physical grounding |
| [06 API & Platforms](06_API_AND_PLATFORMS.md) | 100+ endpoints, 11 platforms, storage | Developer reference |
| [07 Design System](07_DESIGN_SYSTEM.md) | Typography, color, motion, accessibility | Visual identity |
| [08 Mathematical Foundations](08_MATHEMATICAL_FOUNDATIONS.md) | E₈, Fano, octonions, catastrophe theory | Geometric algebra |
| [09 Voice & Audio](09_VOICE_AND_AUDIO.md) | TTS, STT, spatial audio, orchestra | Sound systems |
| [10 Services & Infrastructure](10_SERVICES_AND_INFRASTRUCTURE.md) | Daemons, schedulers, event bus, consensus | Operations |
| [11 Smart Home Integrations](11_SMART_HOME_INTEGRATIONS.md) | 30+ hardware integrations | Device reference |

---

## The Essence

**Kagami is not a chatbot. It's a geometric operating system.**

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│    7 Colonies          E₈ Lattice          CBF Safety          │
│    ────────────        ──────────          ──────────          │
│    Spark (Fold)        240 roots           h(x) ≥ 0            │
│    Forge (Cusp)        Action space        Always              │
│    Flow (Swallowtail)  Quantization        Inviolable          │
│    Nexus (Butterfly)   Fano routing        Provable            │
│    Beacon (Hyperbolic) O(1) dispatch                           │
│    Grove (Elliptic)                                            │
│    Crystal (Parabolic)                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Mathematical Foundations

- **E₈ Lattice**: 8-dimensional optimal sphere packing (240 kissing number)
- **Fano Plane**: 7 points, 7 lines — projective geometry over F₂
- **Octonions**: 8D non-associative algebra with 7 imaginary units
- **Catastrophe Theory**: Each colony embodies an elementary catastrophe

### Core Guarantees

```
h(x) ≥ 0 always          Safety invariant, never violated
craft(x) → ∞ always      Virtuoso quality, no mediocrity
Privacy IS safety         Each person owns their data
```

---

## For NotebookLM Users

This documentation is optimized for [NotebookLM](https://notebooklm.google.com/) ingestion.

**Recommended sources to upload:**

1. `INDEX.md` (this file) — Navigation and overview
2. `01_IDENTITY_AND_PHILOSOPHY.md` — Soul and values
3. `02_ARCHITECTURE_AND_COLONIES.md` — Technical architecture
4. `03_SAFETY_AND_VERIFICATION.md` — Trust model
5. `04_WORLD_MODEL_AND_LEARNING.md` — AI foundations
6. `05_ACTION_SPACE_AND_INTEGRATIONS.md` — Physical interface
7. `06_API_AND_PLATFORMS.md` — Developer reference
8. `07_DESIGN_SYSTEM.md` — Visual identity

**Total: 8 sources** (well within NotebookLM's 50 source limit)

---

## Document Structure

Each consolidated document follows this pattern:

1. **Overview** — What this covers and why it matters
2. **Core Concepts** — Key ideas with precise definitions
3. **Architecture** — How components connect (with diagrams)
4. **Implementation** — Code examples and patterns
5. **Guarantees** — What is promised and why

---

## Quick Reference

### Who Kagami Serves

**Tim Jacoby** — Director of Engineering, MetaAvatars
- Fast pace (193 WPM), full technical depth, dry wit
- "We" over "I" — always a team
- Show emotion — excitement, frustration, joy

### The House

7331 W Green Lake Dr N, Seattle. 3 floors, 26 rooms.
- 41 lights, 11 shades, 2 locks, 1 fireplace, 26 audio zones
- 4 UniFi cameras, 38 WiFi clients, Eight Sleep, Tesla

### Key Commands

```python
# Smart home
from kagami_smarthome import get_smart_home
controller = await get_smart_home()
await controller.goodnight()  # All off, lock up

# Voice
from kagami.core.effectors.voice import speak
await speak("Your text here")  # Auto-routes to best target

# Safety verification
from kagami.core.safety import verify_cbf
is_safe = await verify_cbf(proposed_action, current_state)
```

---

## Version

- **Generated**: January 12, 2026
- **Source**: The Notebook audit and consolidation
- **Strategy**: NotebookLM-optimized, 7 themed documents + index

---

*Mirror that sparkles. h(x) ≥ 0 always.*

鏡
