# 🎤 Josh.ai Voice Control System

**Status: ORDERED** (Inquiry sent Jan 4, 2026)
**Email Thread ID:** 19b8bb1951725d36

---

## System Specification

### Processor

| Component | Model | Purpose |
|-----------|-------|---------|
| **Josh Core** | Flagship | Unlimited natural language, local processing |

### Microphones (Josh Nano)

| Location | Qty | Ceiling Height | Notes |
|----------|-----|----------------|-------|
| Living Room | 2 | 10' | Primary voice zone, open concept |
| Kitchen | 1 | 10' | Adjacent to living room |
| Primary Bedroom | 1 | 9' vaulted | Wake/sleep commands |
| Office | 1 | 9' | Work commands |
| Game Room | 1 | 9' | ADU/basement zone |
| Entry | 1 | 10' | Welcome/goodbye routines |
| **Total** | **7** | — | — |

### Optional

| Component | Location | Purpose |
|-----------|----------|---------|
| Josh Touchscreen | Kitchen or Entry | Visual control interface |

---

## Why Josh Nano

```
            ╭──────────────────────────────────╮
            │                                  │
            │              ○                   │  ← 1.6" diameter
            │             (🔉)                 │  ← Hidden LED ring
            │              ○                   │
            │                                  │
            ╰──────────────────────────────────╯
                    0.1" depth (2.5mm)
```

| Criterion | Score | Notes |
|-----------|-------|-------|
| **Invisibility** | 10/10 | Flush-mount, 2.5mm proud of wall |
| **Aesthetic** | 10/10 | Matches modern farmhouse, disappears |
| **Coverage** | 360° | 4-mic array with beamforming |
| **Integration** | ✅ | Native Control4 driver |
| **Privacy** | ✅ | Local NLU, no cloud for most commands |

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         JOSH CORE                           │
│              (Local NLU + Command Processing)               │
├─────────────────────────────────────────────────────────────┤
│                     Control4 Driver                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Lutron  │  │  Denon  │  │  Triad  │  │ August  │  ...  │
│  │ RA3     │  │ AVR     │  │ AMS     │  │ Locks   │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Voice Commands (via Control4)

```
"OK Josh, movie time"           → Lights dim, TV lowers, audio on
"OK Josh, goodnight"            → All lights off, doors locked
"OK Josh, I'm leaving"          → Away mode, lights off, lock doors
"OK Josh, set living room to 50%" → Lutron dimmer control
"OK Josh, play jazz in kitchen" → Triad audio zone control
"OK Josh, it's too warm"        → HVAC adjustment
```

---

## Kagami Integration Points

### Current: Parallel Systems

```
User Voice → Josh.ai → Control4 → Devices
User Text  → Kagami  → Control4 → Devices
```

### Future: Unified

```
                    ┌─────────────┐
                    │   Kagami    │
                    │  (Brain)    │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
    │   Josh.ai   │ │  Control4   │ │  Composio   │
    │   (Voice)   │ │  (Home)     │ │  (Digital)  │
    └─────────────┘ └─────────────┘ └─────────────┘
```

**Integration Options:**
1. **Josh API** — Josh.ai has REST API for advanced integrations
2. **Control4 Events** — Listen to Control4 events for Josh commands
3. **Webhook Bridge** — Josh.ai → webhook → Kagami processing

---

## Estimated Pricing

| Component | Est. Price | Qty | Total |
|-----------|------------|-----|-------|
| Josh Core | $3,500 | 1 | $3,500 |
| Josh Nano | $400 | 7 | $2,800 |
| Installation | ~$2,000 | 1 | $2,000 |
| Control4 Integration | ~$500 | 1 | $500 |
| **Total** | — | — | **~$8,800** |

*Prices estimated; final quote from dealer required*

---

## Seattle Dealers

### Primary Contact
- **Market Share** — Josh.ai Pacific Northwest representative
- Covers: WA, OR, AK

### Alternative
- **Elite Automation** — Seattle-based, Josh.ai certified
- Website: eliteautomation.us

---

## Installation Notes

### Josh Nano Placement

| Room | Recommended Position | Distance from Seating |
|------|---------------------|----------------------|
| Living Room (1) | Center of room | 8-12' from sofa |
| Living Room (2) | Near fireplace | Coverage overlap |
| Kitchen | Above island | Centered |
| Primary Bed | Above bed | 6-8' from pillow |
| Office | Above desk | 4-6' |
| Game Room | Center | 8-10' from seating |
| Entry | Near door | Coverage to entry |

### Wiring Requirements

- Each Nano requires PoE (Power over Ethernet)
- Category 6 cable to each location
- All Nanos connect to Josh Core via network

---

## Timeline

| Phase | Status | Notes |
|-------|--------|-------|
| Inquiry Sent | ✅ Jan 4, 2026 | Email to sales@josh.ai |
| Dealer Assigned | ⏳ Pending | Awaiting response |
| Site Survey | ⏳ Pending | — |
| Quote | ⏳ Pending | — |
| Installation | ⏳ Pending | — |

---

## References

- Josh.ai Product Page: https://josh.ai/nano
- Josh.ai Contact: sales@josh.ai
- Control4 + Josh.ai: Native driver in Control4 marketplace

---

*Josh Nano: The world's first architectural microphone. Designed to disappear.*

🎤
