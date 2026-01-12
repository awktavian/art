# Kagami Orb — Component Alternatives

## Purpose

This document provides alternative components for each major subsystem. Use when:
- Primary component is unavailable
- Cost reduction is needed
- Performance requirements change
- Sourcing difficulties arise

---

## Compute Module

| Option | Model | RAM | Storage | WiFi | Price | Notes |
|--------|-------|-----|---------|------|-------|-------|
| **Primary** | CM4 Lite 4GB | 4GB | microSD | No | $45 | Recommended |
| Alt 1 | CM4 8GB | 8GB | eMMC | Optional | $75 | More headroom |
| Alt 2 | Pi 4 Model A+ | 4GB | microSD | Yes | $35 | Larger, easier I/O |
| Alt 3 | Orange Pi 5 | 4-16GB | eMMC | Yes | $60-100 | RK3588S, faster |
| Alt 4 | Radxa CM5 | 4-8GB | eMMC | Yes | $50-80 | CM4 compatible |

**Trade-offs:**
- CM4 Lite: Smallest, proven ecosystem, no onboard WiFi
- Pi 4 A+: Larger form factor, built-in connectors
- Orange Pi 5: Faster CPU, less community support
- Radxa CM5: Newer, pin-compatible, untested

---

## AI Accelerator

| Option | Model | Performance | Power | Interface | Price | Notes |
|--------|-------|-------------|-------|-----------|-------|-------|
| **Primary** | Google Coral USB | 4 TOPS | 2.5W | USB 3.0 | $60 | Proven |
| Alt 1 | Coral M.2 A+E | 4 TOPS | 2W | M.2 | $35 | Needs adapter |
| Alt 2 | Hailo-8L | 13 TOPS | 2.5W | M.2 | $50 | Higher performance |
| Alt 3 | None (CPU only) | ~0.5 TOPS | 0W | - | $0 | Slower inference |

**Trade-offs:**
- Coral USB: Easy, proven, takes USB port
- Coral M.2: More compact, needs carrier support
- Hailo-8L: Faster, less mature SDK
- CPU only: Simplest, 10x slower wake word

---

## Microphone Array

| Option | Model | Channels | DSP | Interface | Price | Notes |
|--------|-------|----------|-----|-----------|-------|-------|
| **Primary** | ReSpeaker 4-Mic | 4 | XMOS | I2S | $35 | Full beamforming |
| Alt 1 | ReSpeaker 2-Mic | 2 | None | I2S | $10 | Basic stereo |
| Alt 2 | SPH0645 × 4 | 4 | None | I2S | $15 | DIY array |
| Alt 3 | Matrix Voice | 8 | ESP32 | USB | $50 | Overkill |

**Trade-offs:**
- ReSpeaker 4-Mic: Best beamforming, proven
- ReSpeaker 2-Mic: Cheaper, less directional
- SPH0645 DIY: Flexible, requires software DSP
- Matrix Voice: Expensive, complex

---

## Wireless Power

| Option | Model | Power | Gap | Frequency | Price | Notes |
|--------|-------|-------|-----|-----------|-------|-------|
| **Primary** | Custom Resonant (80mm Litz @ 140kHz) | 15W | 15mm | ~140kHz | $80 pair | k≈0.82, ~75% eff |
| Alt 1 | Resonant 30W (6.78MHz) | 30W | 20mm | 6.78MHz | $100 pair | Higher gap, expensive |
| Alt 2 | Wired (USB-C) | 30W | 0mm | - | $5 | No levitation gap |
| ~~Rejected~~ | ~~Qi EPP 15W~~ | ~~15W~~ | ~~15mm~~ | ~~87-205kHz~~ | ~~$50 pair~~ | ~~FOD false alarms~~ |

**Why Custom Resonant over Qi EPP:**
- **Gap Issue:** Qi EPP at 15mm gap with maglev magnets causes FOD (Foreign Object Detection) false alarms
- **Magnet Interference:** Maglev's permanent magnets trip Qi's metal detection circuitry
- **Solution:** Custom resonant coupling with 80mm Litz coils tuned to ~140kHz achieves k≈0.82 coupling coefficient
- **Efficiency:** 20W TX → 15W RX (~75% efficiency at 15mm gap)

**Trade-offs:**
- Custom Resonant 80mm: Designed for 15mm gap with maglev, requires custom coils
- Resonant 6.78MHz: Better gap tolerance, more expensive, overkill for this application
- Wired: Backup only, defeats levitation

---

## Levitation Module

| Option | Model | Capacity | Gap | Power | Price | Notes |
|--------|-------|----------|-----|-------|-------|-------|
| **Primary** | ZT-HX500 | 500g | 15mm | 20W | $180 | Balanced |
| Alt 1 | ZT-HX300 | 300g | 12mm | 15W | $120 | Lighter orb |
| Alt 2 | DIY coils | 400g | 10-20mm | 25W | $50 | Complex |
| Alt 3 | Static base | N/A | 0mm | 0W | $0 | No levitation |

**Trade-offs:**
- ZT-HX500: Good capacity, proven
- ZT-HX300: Cheaper, must reduce orb weight
- DIY: Flexible, significant engineering
- Static: Fallback, loses "magic"

---

## Battery Pack

| Option | Chemistry | Capacity | Voltage | Weight | Price | Notes |
|--------|-----------|----------|---------|--------|-------|-------|
| **Primary** | Li-Po 3S | 10,000mAh | 11.1V | 180g | $45 | ~5hr runtime |
| Alt 1 | Li-Po 3S | 6,000mAh | 11.1V | 110g | $30 | ~3hr runtime |
| Alt 2 | LiFePO4 3S | 6,000mAh | 9.6V | 200g | $50 | Safer |
| Alt 3 | 18650 3S3P | 9,000mAh | 11.1V | 270g | $35 | Heavier, robust |

**Trade-offs:**
- Li-Po 10Ah: Best runtime, moderate weight
- Li-Po 6Ah: Lighter, shorter runtime
- LiFePO4: Safest, lower voltage, heavier
- 18650: Cheapest cells, heaviest

---

## LED Ring

| Option | Model | LEDs | Type | Interface | Price | Notes |
|--------|-------|------|------|-----------|-------|-------|
| **Primary** | SK6812 RGBW | 24 | Ring | SPI | $12 | White channel |
| Alt 1 | WS2812B RGB | 24 | Ring | SPI | $8 | No white |
| Alt 2 | APA102 | 24 | Ring | SPI | $15 | Faster refresh |
| Alt 3 | SK6812 Mini | 60 | Strip | SPI | $18 | Higher density |

**Trade-offs:**
- SK6812 RGBW: White for true color mixing
- WS2812B: Cheaper, RGB only
- APA102: Faster data rate, 2 wires
- SK6812 Mini: More LEDs, higher power

---

## WiFi Module

| Option | Model | Standard | Band | Interface | Price | Notes |
|--------|-------|----------|------|-----------|-------|-------|
| **Primary** | Intel AX210 | WiFi 6E | Tri-band | M.2 | $20 | 6GHz support |
| Alt 1 | CM4 onboard | WiFi 5 | Dual-band | Built-in | $0 | CM4 variant |
| Alt 2 | RTL8852 | WiFi 6 | Dual-band | USB | $15 | No 6GHz |
| Alt 3 | ESP32-S3 | WiFi 4 | 2.4GHz | UART | $5 | Backup only |

**Trade-offs:**
- AX210: Best performance, 6GHz
- CM4 onboard: Simplest, need CM4 WiFi variant
- RTL8852: Good performance, no 6GHz
- ESP32-S3: Emergency backup only

---

## Shell Materials

| Option | Material | Dia | Thickness | Finish | Price | Notes |
|--------|----------|-----|-----------|--------|-------|-------|
| **Primary** | Acrylic | 120mm | 3mm | Clear | $50/pair | Standard |
| Alt 1 | Acrylic | 100mm | 3mm | Clear | $35/pair | Smaller |
| Alt 2 | Glass | 120mm | 2mm | Clear | $100/pair | Premium |
| Alt 3 | 3D printed | 120mm | 2mm | Smooth | $30 | Custom shapes |

**Trade-offs:**
- Acrylic 120mm: Good size, available
- Acrylic 100mm: Tighter fit, lighter
- Glass: Beautiful, fragile
- 3D printed: Custom, not as clear

---

## Base Enclosure

| Option | Material | Method | Price | Notes |
|--------|----------|--------|-------|-------|
| **Primary** | Walnut | CNC | $40 + $150 | Premium look |
| Alt 1 | Aluminum | CNC | $30 + $100 | Industrial |
| Alt 2 | 3D Print | FDM/SLA | $20 | Prototype |
| Alt 3 | Wood box | Manual | $20 | Simple |

**Trade-offs:**
- Walnut CNC: Best aesthetics, expensive labor
- Aluminum: Durable, cold feel
- 3D Print: Quick iteration
- Wood box: Easiest, less refined

---

## Decision Matrix

Use this when selecting alternatives:

| Factor | Weight | Primary | Alt 1 | Alt 2 |
|--------|--------|---------|-------|-------|
| **Cost** | 20% | | | |
| **Availability** | 15% | | | |
| **Performance** | 25% | | | |
| **Integration** | 20% | | | |
| **Risk** | 20% | | | |
| **TOTAL** | 100% | | | |

Score each option 1-5 (5 = best), multiply by weight, sum for total.

---

## Recommended Simplified Build

If budget or complexity is a concern, this simplified configuration works:

| Component | Simplified Choice | Savings |
|-----------|-------------------|---------|
| Compute | Pi 4 Model A+ | +$10 |
| AI | CPU only | +$60 |
| Mic | ReSpeaker 2-Mic | +$25 |
| Battery | 6,000mAh | +$15 |
| Shell | 100mm acrylic | +$15 |
| Base | 3D printed | +$170 |
| **TOTAL SAVINGS** | | **~$295** |

**Simplified Orb Cost: ~$575 (vs $870)**

Limitations:
- Slower wake word detection
- Less directional voice
- Shorter battery life (~2.5 hours)
- Smaller visual presence

---

```
h(x) ≥ 0. Always.

Options exist.
Trade-offs are real.
The mirror adapts.

鏡
```
