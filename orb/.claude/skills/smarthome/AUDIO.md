# 🔊 Audio System — KEF Reference 5.2.4 Dolby Atmos

**7331 W Green Lake Dr N • Bob's Smart Home Installation**

---

## Home Theater (Living Room)

### KEF Reference 5.2.4 Dolby Atmos

**Configuration:** 5.2.4 THX-certified Dolby Atmos

| Channel | Speaker | Model | Finish |
|---------|---------|-------|--------|
| **Front L/R** | KEF Reference 5 Meta | Floorstanding | High Gloss White/Blue |
| **Center** | KEF Reference 1 Meta | Bookshelf (on stand) | High Gloss White/Blue |
| **Surround L/R** | KEF Reference 1 Meta | Bookshelf (on stand) | High Gloss White/Blue |
| **Height 1-4** | KEF CI200RR-THX | In-ceiling | THX Ultra Certified |

### Subwoofers

| Model | Type | Quantity |
|-------|------|----------|
| **KEF CI3160RLB-THX** | THX Extreme In-Wall | 2 |
| **KEF KASA500** | Subwoofer Amplifier | 1 |

### Speaker Stands

| Model | Finish | Quantity |
|-------|--------|----------|
| KEF Reference 1 Meta Stand | Mineral White | 2 |

---

## Amplification

| Model | Type | Channels |
|-------|------|----------|
| **Episode EA-DYN12D-100** | Dynamic Series Class-D | 12 ch |
| **Episode EA-DYN-8D100** | Dynamic Series Class-D | 8 ch |

**Total amplifier channels:** 20

---

## Audio Matrix

| Model | Capabilities |
|-------|--------------|
| **Triad TS-AMS16** | 16-Source, 16-Zone Matrix Switch |

---

## Distributed Audio (26 Zones)

**Speaker Model:** Monitor Audio Creator Series C2M-CP (In-ceiling Two-way)

| Floor | Zones |
|-------|-------|
| **Basement** | Office/Gym, Under Stairway, AADU Rec Room, Patio |
| **Main Floor** | Kitchen, Entry, Living, Dining, Deck, Mudroom, Powder Room |
| **Upper Floor** | Primary Bed, Primary Bath, Primary Closet, Loft, Bed 2, Bed 3, Bed 4, Bath 3, Bath 4, Office, Office Bath |

### Outdoor Speakers

| Location | Model |
|----------|-------|
| Deck | Monitor Audio C2M-CP |
| Patio | Monitor Audio CL2 M (Climate Series, Weatherproof) |

---

## Rough-In Infrastructure

| Component | Model | Quantity |
|-----------|-------|----------|
| Speaker Rough-In Frame | KEF RIF200R | 50 |
| 200 Square Rough-In Frame | KEF RIF200S | 1 pair |
| Pre-Construction Bracket | Monitor Audio CM-B (Purple) | Multiple |

---

## Pre-Wire

| Type | Specification |
|------|---------------|
| **5.2.4 Dolby Atmos** | 14 gauge, home run to MEC |
| **Distributed Audio** | 14 gauge 4-conductor |
| **Subwoofer** | Dedicated runs |

**MEC Location:** Closet under stairway (Basement)

---

## KEF Reference Series Specifications

### Reference 5 Meta (Front L/R)

- **Type:** 3-way bass reflex
- **Drivers:** 1x 1" Uni-Q with MAT, 4x 6.5" hybrid aluminum
- **Frequency:** 40Hz - 50kHz
- **Sensitivity:** 87dB
- **Impedance:** 4Ω
- **Finish:** High Gloss White/Blue

### Reference 1 Meta (Center/Surround)

- **Type:** 2-way bass reflex
- **Drivers:** 1x 1" Uni-Q with MAT, 1x 6.5" hybrid aluminum
- **Frequency:** 58Hz - 50kHz  
- **Sensitivity:** 85dB
- **Impedance:** 4Ω
- **Finish:** High Gloss White/Blue

### CI200RR-THX (Atmos Height)

- **Type:** In-ceiling, THX Ultra Certified
- **Drivers:** 8" Uni-Q array
- **Certification:** THX Ultra
- **Use:** Dolby Atmos height channels

### CI3160RLB-THX (Subwoofer)

- **Type:** In-wall, THX Extreme Certified
- **Drivers:** 3x 6.5" forced-canceling array
- **Frequency:** 25Hz - 140Hz
- **Power:** Up to 500W recommended

---

## Control Integration

### Via Control4

```python
from kagami_smarthome.integrations.control4 import Control4Integration

# Audio zone control (26 zones via Triad AMS16)
await c4.set_audio_zone_volume("Living Room", 40)
await c4.play_source("Living Room", "Sonos")

# Home theater
await c4.activate_scene("Movie Night")  # Dims lights, sets audio mode
```

### Denon AVR Control

```python
from kagami_smarthome.integrations.denon import DenonIntegration

# Direct AVR control
await denon.set_surround_mode("DOLBY ATMOS")
await denon.set_volume(-35)  # dB
await denon.select_input("HEOS")
```

---

## Notes

- THX-certified system for reference-level performance
- KEF Meta technology for reduced distortion
- In-wall subwoofers provide clean aesthetics with massive bass
- 5.2.4 configuration optimal for the living room dimensions
- Distributed audio separate from home theater (26 zones)

---

## Related Documentation

| Document | Content |
|----------|---------|
| `SENSORY.md` | Full audio I/O map (inputs + outputs) |
| `SPECIFICATIONS.md` | All appliance specs |
| `HOME.md` | Room layout and spatial awareness |

---

鏡
