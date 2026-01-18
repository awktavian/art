# Kagami Orb — PCB Schematic Completion Plan

**Status:** Symbols placed (35%) → Need wiring, passives, review (100%)
**Estimated Effort:** 40-60 hours (2-3 weeks part-time)
**Prerequisite:** Thermal FEA validation (go/no-go for 85mm design)

---

## Current State Assessment

| Sheet | File | Symbols | Wires | Passives | Status |
|-------|------|---------|-------|----------|--------|
| 1 - Top Level | `kagami_orb.kicad_sch` | 6 | 2 | 0 | 15% — Needs hierarchy |
| 2 - Power | `kagami_orb_power.kicad_sch` | 11 | 0 | 0 | 35% — Symbols placed |
| 3 - QCS6490 | `kagami_orb_qcs6490.kicad_sch` | 7 | 0 | 0 | 30% — Symbols placed |
| 4 - USB Hub | `kagami_orb_usb.kicad_sch` | 3 | 0 | 0 | 20% — Incomplete |
| 5 - Audio | `kagami_orb_audio.kicad_sch` | 3 | 0 | 0 | 20% — Incomplete |
| 6 - LED | `kagami_orb_led.kicad_sch` | 4 | 0 | 0 | 25% — Basic |
| 7 - Sensors | `kagami_orb_sensors.kicad_sch` | 4 | 0 | 0 | 20% — Incomplete |

**What's Done:**
- Project structure created
- Major ICs placed with correct footprints
- Power labels defined
- Section labels added

**What's Missing:**
- Wire connections between all components
- Passive components (capacitors, resistors, inductors)
- Protection circuits (TVS, ESD, fuses)
- Test points and debug headers
- Decoupling capacitors on all power pins
- Crystal/oscillator for USB hub
- I2C pull-ups
- Boot configuration resistors
- Thermal pad connections

---

## Phase 1: Symbol Library Completion (8-12 hours)

### 1.1 Create Missing Symbols (kagami_orb.kicad_sym)

| Symbol | Package | Pins | Notes |
|--------|---------|------|-------|
| `BQ25895` | QFN-24 | 24 | Complete with thermal pad |
| `BQ40Z50` | QFN-32 | 32 | SBS 1.1 compliant pinout |
| `TPS62840` | SOT-23-6 | 6 | 60nA IQ regulator |
| `TPS62841` | SOT-23-6 | 6 | 1.8V variant |
| `USB2514B` | QFN-36 | 36 | 4-port USB hub |
| `MAX98357A` | QFN-16 | 16 | I2S Class-D amp |
| `74AHCT125` | TSSOP-14 | 14 | Level shifter |
| `DRV5053` | SOT-23 | 3 | Hall sensor |
| `TMP117` | SOT-563 | 6 | I2C temp sensor |
| `QCS6490_CONN` | DF40 100-pin | 200 | 2× connectors |
| `PMEG2010` | SOD-323 | 2 | Schottky diode |
| `SMBJ5.0A` | SMB | 2 | TVS diode |

### 1.2 Footprint Verification

Verify all footprints exist in KiCad standard library or create custom:
- [ ] QFN-24-1EP_4x4mm (BQ25895)
- [ ] QFN-32-1EP_5x5mm (BQ40Z50)
- [ ] QFN-36 (USB2514B) — May need custom
- [ ] DF40HC(3.0)-100DS-0.4V — Custom required for QCS6490

---

## Phase 2: Power Management Sheet (10-15 hours)

### 2.1 Input Protection

```
J6 (Resonant) ─┬─ D1 (PMEG2010) ─ F1 (500mA PTC) ─┬─ VIN_RES
               │                                    │
               └─ C1 (10μF ceramic)                └─ D2 (SMBJ5.0A TVS)
                                                    │
                                                   GND
```

### 2.2 BQ25895 Charger Circuit

**Required Passives:**
| Ref | Value | Purpose |
|-----|-------|---------|
| C_PMID | 10μF | PMID decoupling |
| C_VBUS | 1μF | VBUS filter |
| C_VSYS | 10μF | System output |
| C_VBAT | 10μF | Battery decoupling |
| R_ILIM | 10kΩ | 3A input limit |
| R_TS | 10kΩ NTC + divider | Thermistor |
| C_REGN | 1μF | Internal regulator |

**Connections:**
- VBUS ← VIN_RES (from resonant) OR VIN_USB (from USB-C)
- VSYS → 5V_SYS rail
- VBAT ↔ J5 Battery connector
- I2C ↔ I2C bus (0x6A)
- INT → GPIO_CHG_INT
- CE ← 3V3 (always enabled)
- QON ← GPIO_SHIP_MODE (low-power mode control)

### 2.3 BQ40Z50 Fuel Gauge Circuit

**Required Passives:**
| Ref | Value | Purpose |
|-----|-------|---------|
| R_SENSE | 5mΩ 1% | Current sense |
| C_BAT | 100nF | Battery filter |
| R_TS | 10kΩ NTC | Cell temperature |

**Connections:**
- BAT ← Battery positive (through sense resistor)
- PACK+ → System load
- SDA/SCL ↔ I2C bus (0x0B)
- ALERT → GPIO_BAT_ALERT (interrupt-driven)

### 2.4 Buck Converters

**TPS62840 (3.3V):**
| Ref | Value | Purpose |
|-----|-------|---------|
| C_IN | 10μF | Input filter |
| C_OUT | 22μF | Output filter |
| L1 | 2.2μH | Inductor (Coilcraft XAL4020) |
| R_FB | Per datasheet | Feedback divider |

**TPS62841 (1.8V):**
- Same topology, different feedback divider

### 2.5 USB-C Emergency Input

```
J1 (USB-C)
   │
   ├─ CC1 ── R (5.1kΩ) ── GND
   ├─ CC2 ── R (5.1kΩ) ── GND
   │
   ├─ VBUS ── D (diode OR) ──┬── VIN_USB
   │                          │
   │                     C (10μF)
   │                          │
   │                         GND
   │
   └─ D+/D- ── USB_DATA_P/N (to QCS6490 via USB hub)
```

---

## Phase 3: QCS6490 Interface Sheet (8-12 hours)

### 3.1 Module Connectors

Two DF40HC(3.0)-100DS connectors (J10, J11) for QCS6490 SoM.

**Pin Groups to Route:**
| Group | Pins | Destination |
|-------|------|-------------|
| Power | VBAT, VDD_CORE, VDD_IO, GND | Power rails |
| USB | USB_DP, USB_DM | USB2514B hub |
| I2S | PCM_CLK, PCM_FS, PCM_DIN, PCM_DOUT | Audio system |
| I2C | SDA, SCL | I2C bus |
| GPIO | 17, 18, 22-24, 27 | Various peripherals |
| MIPI | DSI lanes | Display (sheet 8 - future) |

### 3.2 Boot Configuration

```
nRPIBOOT ── R1 (10kΩ) ── 3V3 (normal boot from eMMC)
GLOBAL_EN ── 3V3 (always enabled)
RUN ── SW1 (soft power button) ── GND with 10kΩ pullup
```

### 3.3 Decoupling Network

**Per power pin:**
- 100nF ceramic (close to pin)
- 10μF bulk (per rail)

**Total for QCS6490:**
- ~20× 100nF 0402
- 4× 10μF 0603

---

## Phase 4: USB Hub Sheet (6-8 hours)

### 4.1 USB2514B Circuit

**Required Components:**
| Ref | Value | Purpose |
|-----|-------|---------|
| Y1 | 24MHz crystal | Clock source |
| C_XTAL | 20pF × 2 | Crystal load |
| R_USB | 15kΩ × 8 | Termination resistors |
| C_VDD | 100nF × 4 | Decoupling |
| C_VBUS | 10μF × 4 | Port power filter |
| R_CFG | Various | Strap configuration |

### 4.2 Downstream Port Allocation

```
USB2514B
    │
    ├─ Port 1 → Hailo-10H M.2 slot (fixed)
    ├─ Port 2 → Intel AX210 WiFi (via adapter)
    ├─ Port 3 → J1 USB-C external (shared with debug)
    └─ Port 4 → J7 Debug header (SWD + serial)
```

### 4.3 Configuration Straps

- NON_REM[4:1] = 1111 (all non-removable)
- PRTPWR[4:1] = GPIO controlled
- GANG = 0 (individual port power)

---

## Phase 5: Audio Sheet (6-8 hours)

### 5.1 sensiBel SBM100B Interface

**8-pin FFC Connector (J2):**
| Pin | Signal | QCS6490 GPIO |
|-----|--------|--------------|
| 1 | 3V3 | Power |
| 2 | GND | Ground |
| 3 | BCK | GPIO12 (I2S_BCLK) |
| 4 | WS | GPIO19 (I2S_LRCLK) |
| 5 | DO | GPIO20 (I2S_DIN) |
| 6 | INT | GPIO24 (VAD interrupt) |
| 7 | SDA | I2C_SDA |
| 8 | SCL | I2C_SCL |

### 5.2 MAX98357A Speaker Amp

**Required Passives:**
| Ref | Value | Purpose |
|-----|-------|---------|
| C_VDD | 10μF + 100nF | Decoupling |
| R_GAIN | Open/GND/100k | Gain select (15dB default) |
| FERRITE | 600Ω@100MHz | Output filtering |

**Connections:**
- BCLK ← GPIO12
- LRCLK ← GPIO19
- DIN ← GPIO21
- SD_MODE → 3V3 (always on, or GPIO for mute)
- OUT+ / OUT- → J4 Speaker connector

---

## Phase 6: LED Control Sheet (4-6 hours)

### 6.1 Level Shifter (74AHCT125)

```
GPIO18 (3.3V) ─── 74AHCT125 ─── 5V_LED_DATA
                    │
              VCC = 5V_LED
              GND = GND
              OE = GND (always enabled)
```

### 6.2 HD108 Connector (J3)

| Pin | Signal | Source |
|-----|--------|--------|
| 1 | 5V | 5V_LED rail |
| 2 | DIN | 5V_LED_DATA |
| 3 | GND | Ground |
| 4 | NC | — |

**Passives:**
- R_SERIES (470Ω) in data line
- C_BYPASS (100nF) at connector

---

## Phase 7: Sensors Sheet (4-6 hours)

### 7.1 Hall Effect Sensor (DRV5053)

```
3V3 ── VCC
        │
       OUT ── GPIO22 (analog capable)
        │
       GND ── GND
```

### 7.2 Temperature Sensor (TMP117)

```
3V3 ── VCC ── C (100nF) ── GND
        │
       SDA ── I2C_SDA (0x48)
       SCL ── I2C_SCL
     ALERT ── GPIO23
        │
       GND ── GND
```

### 7.3 I2C Bus Pull-ups

```
3V3 ── R1 (4.7kΩ) ──┬── I2C_SDA
3V3 ── R2 (4.7kΩ) ──┼── I2C_SCL
                    │
           (to all I2C devices)
```

**I2C Address Map:**
| Address | Device |
|---------|--------|
| 0x0B | BQ40Z50 |
| 0x35 | sensiBel SBM100B |
| 0x48 | TMP117 |
| 0x6A | BQ25895 |

---

## Phase 8: Design Review & DRC (6-10 hours)

### 8.1 Electrical Rule Check (ERC)

- [ ] All power pins connected
- [ ] No floating inputs
- [ ] All nets have at least 2 connections
- [ ] Power symbols correctly assigned
- [ ] No duplicate reference designators

### 8.2 BOM Review

- [ ] All components have valid MPN
- [ ] Footprints match package
- [ ] Values specified for all passives
- [ ] Datasheet links valid

### 8.3 Peer Review Checklist

- [ ] Power sequencing correct (5V → 3.3V → 1.8V)
- [ ] I2C addresses don't conflict
- [ ] GPIO assignments match firmware
- [ ] Thermal considerations (exposed pads grounded)
- [ ] ESD protection on external interfaces

---

## Phase 9: PCB Layout Preparation (4-6 hours)

### 9.1 Board Outline

- Circular 60mm diameter (fits inside 85mm sphere)
- 4-layer stackup: Signal / GND / Power / Signal
- 1.6mm thickness

### 9.2 Component Placement Strategy

```
        TOP VIEW (60mm circular)

              USB-C (J1)
                 │
    ┌────────────┴────────────┐
    │      QCS6490 MODULE     │
    │     (J10/J11 center)    │
    │                         │
 LED├─  USB2514B    BQ25895 ─┤ Battery
    │                         │
    │   TPS62840   BQ40Z50   │
    │   TPS62841             │
    │                         │
    │    Sensors (edge)       │
    └────────────┬────────────┘
                 │
            Audio (J2, J4)
```

### 9.3 Critical Routing

1. **USB pairs** — 90Ω differential, matched length
2. **I2S signals** — Short traces, ground guard
3. **Power planes** — Split for 5V/3.3V/1.8V
4. **Thermal vias** — Under QCS6490 module

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| **1. Symbol Library** | 8-12h | None |
| **2. Power Sheet** | 10-15h | Phase 1 |
| **3. QCS6490 Sheet** | 8-12h | Phase 1 |
| **4. USB Hub Sheet** | 6-8h | Phase 1 |
| **5. Audio Sheet** | 6-8h | Phase 1 |
| **6. LED Sheet** | 4-6h | Phase 1 |
| **7. Sensors Sheet** | 4-6h | Phase 1 |
| **8. Review & DRC** | 6-10h | Phases 2-7 |
| **9. Layout Prep** | 4-6h | Phase 8 |
| **TOTAL** | **56-83h** | |

**Realistic Timeline:**
- Part-time (20h/week): **3-4 weeks**
- Full-time (40h/week): **1.5-2 weeks**
- With contractor: **1 week** (parallelize)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Thermal FEA fails | Block schematic completion until validated |
| sensiBel lead time | Design socket for alternate Infineon IM69D130 |
| QCS6490 pinout changes | Use TurboX reference schematic |
| USB hub EMI | Add common-mode chokes if needed |
| I2C bus issues | Design in optional I2C buffer |

---

## Recommended Next Steps

1. **TODAY:** Respond to George Laird (thermal FEA)
2. **This Week:** Complete Phase 1 (symbol library)
3. **Block:** Don't start layout until thermal FEA passes
4. **Parallel:** Order sensiBel samples (8-week lead time)

---

```
鏡

h(x) ≥ 0. Always.
Every net has purpose.
The schematic is the truth.
```
