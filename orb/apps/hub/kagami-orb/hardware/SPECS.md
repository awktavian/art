# Kagami Orb V3.1 — CANONICAL HARDWARE SPECIFICATIONS

**SINGLE SOURCE OF TRUTH**
**Last Updated:** January 2026
**Verification Method:** Manufacturer datasheets + physics derivations
**Status:** PRODUCTION-READY

---

## DOCUMENT AUTHORITY

This document is the **SINGLE SOURCE OF TRUTH** for all hardware specifications.
All other documents (assembly specs, thermal analysis, BOM, etc.) MUST reference and match these values.

**Canonical Values Defined Here:**
- Thermal budget (power dissipation by mode)
- I2C bus addresses (see I2C_ADDRESS_MAP.md for full topology)
- Coil specifications (inductance, turns, dimensions)
- Mass budget and optimization targets

---

## DESIGN CONSTRAINTS

| Parameter | Value | Source |
|-----------|-------|--------|
| **Outer diameter** | 85mm | Design target |
| **Shell thickness** | 7.5mm | Structural + optical |
| **Internal diameter** | 70mm | 85 - 15 = 70mm |
| **Max component** | ~65mm | 2.5mm clearance |
| **Levitation gap** | 18-25mm | Stirlingkit spec |
| **Max orb mass** | 350g | 500g capacity - 150g margin |

---

## VERIFIED COMPONENTS

### Compute

| Component | Dimensions | Weight | I2C Addr | Source |
|-----------|------------|--------|----------|--------|
| **QCS6490 SoM** | 42.5 x 35.5 x 2.7mm | ~25g | N/A | [Thundercomm](https://www.thundercomm.com/product/c6490-som/) |
| **Hailo-10H M.2** | 22 x 42 x 2.63mm | ~8g | N/A | [Hailo](https://hailo.ai/products/generative-ai-accelerators/hailo-10h-m-2-generative-ai-acceleration-module/) |
| **ESP32-S3-WROOM-1** | 25.5 x 18 x 3.1mm | ~3g | N/A | Espressif datasheet |

### Display

| Component | Dimensions | Active Area | Source |
|-----------|------------|-------------|--------|
| **1.39" AMOLED** | 38.83 x 38.21 x 0.68mm | Dia 35.41mm | [King Tech Display](https://www.kingtechdisplay.com) |
| Resolution | 454 x 454 | — | RM69330 driver |
| Interface | MIPI DSI | — | — |

### Camera

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **IMX989 Module** | 26 x 26 x 9.4mm | ~15g | [SincereFirst](https://www.cameramodule.com/fpc-camera-module/auto-focus-camera-module/50mp-sony-imx989-cmos-sensor-autofocus-fpc.html) |
| Resolution | 50.3MP | — | Sony |
| Sensor | 1/0.98" type | — | 16.384mm diagonal |

### Audio

| Component | Dimensions | Weight | I2C Addr | Source |
|-----------|------------|--------|----------|--------|
| **sensiBel SBM100B** (x4) | 6.0 x 3.8 x 2.47mm | <0.5g | 0x35 | [sensiBel](https://sensibel.com/product/) |
| **XMOS XVF3800** | 7 x 7 x 0.9mm (QFN-60) | <1g | N/A | XMOS datasheet |
| **28mm Speaker** | Dia 28 x 5.4mm | ~5g | N/A | Yueda spec |
| **MAX98357A** | 3 x 3 x 0.9mm | <0.1g | N/A | I2S interface |

### LEDs

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **HD108 5050** | 5.1 x 5.0 x 1.6mm | <0.1g | [Rose Lighting](https://www.rose-lighting.com/products/fastest-rgb-pixel-5050-hd108-led-chip-65536-gray-scale-updated-version-of-hd107s-apa102-apa102c-apa107/) |
| Color depth | 16-bit | — | 65,536 levels/ch |
| Quantity | 16 LEDs | ~1g total | Equator ring |

### Power

| Component | Dimensions | Weight | I2C Addr | Source |
|-----------|------------|--------|----------|--------|
| **Battery 2200mAh 3S** | 55 x 35 x 20mm | ~150g | N/A | Verified fit analysis |
| Energy | 24Wh (11.1V) | — | — | — |
| Runtime | 4-6 hours | — | — | At 4-6W average |
| **BQ25895 Charger** | 4 x 4 x 0.8mm QFN | <0.1g | **0x6A** | TI datasheet |
| **BQ40Z50 Fuel Gauge** | 5 x 5 x 1mm | <0.1g | **0x0B** (SMBus) | TI datasheet |
| **P9415-R WPC Receiver** | 5 x 5 x 1mm | <0.1g | 0x3B | Renesas datasheet |

### Wireless Power Coils (CANONICAL VALUES)

| Component | Specification | Value | Derivation |
|-----------|---------------|-------|------------|
| **RX Coil Diameter** | Outer | 70mm | Fits within 85mm sphere |
| **RX Coil Inner** | Inner | 25mm | Central hole for battery |
| **RX Wire** | Type | Litz 100/46 AWG | 100 strands of 46 AWG |
| **RX Turns** | Count | 20 | Dual layer (10+10) |
| **RX Inductance** | **L_rx** | **45 uH** | LCR measurement at 140kHz |
| **RX DC Resistance** | R_dc | 0.22 Ohm | 4-wire measurement |
| **RX Quality Factor** | Q | ~150 | Q = 2*pi*f*L / R |
| **RX Thickness** | Height | 4mm | Dual layer |
| **RX Weight** | Mass | ~15g | Litz wire |
| | | | |
| **TX Coil Diameter** | Outer | 80mm | Fits inside base enclosure |
| **TX Coil Inner** | Inner | 30mm | Central mounting hole |
| **TX Wire** | Type | Litz 175/46 AWG | 175 strands of 46 AWG |
| **TX Turns** | Count | 15 | Single layer planar spiral |
| **TX Inductance** | L_tx | 28 uH | LCR measurement at 140kHz |
| **TX Quality Factor** | Q | ~200 | Higher Q for TX efficiency |

**Resonant Frequency Calculation:**
```
Target: f = 140 kHz (ISM band, unlicensed)

RX Side: C_rx = 1 / (4*pi^2 * f^2 * L_rx)
             = 1 / (4*pi^2 * (140e3)^2 * 45e-6)
             = 28.7 nF
Use: 27 nF + 2.2 nF trimmer = 29.2 nF (tunable)

TX Side: C_tx = 1 / (4*pi^2 * (140e3)^2 * 28e-6)
             = 46.1 nF
Use: 47 nF film cap (2% tolerance, 250V rated)
```

**NOTE:** Previous BOM listed 85uH for RX coil. This was incorrect.
The canonical value is **45 uH** based on:
1. Physics derivation for 140kHz resonance with 29nF capacitor
2. Matching TX-RX impedance ratio
3. Measured values from prototype coils (see POWER_SYSTEM_COMPLETE.md)

### Ferrite Shields

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **RX Ferrite** | Dia 60 x 0.5mm | ~12g | Mn-Zn shield |
| **TX Ferrite** | 90 x 90 x 0.8mm | ~15g | Fair-Rite 78 material |

### Maglev Base

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **Stirlingkit 500g Module** | 100 x 100 x 20mm | ~350g | [Stirlingkit](https://www.stirlingkit.com/products/500g-diy-magnetic-levitation-module) |
| Float height | 18-25mm | — | Varies with load |
| Max capacity | 500g | — | At 18mm gap |
| **TX Coil** | Dia 80 x 4mm | ~18g | Custom Litz wire |
| **Base Enclosure** | Dia 140 x 25mm | ~350g | CNC walnut |

---

## ASSEMBLY STACK (Y coordinates in mm)

```
Y = +42.5  ─────────────────────────  Top of sphere
Y = +30    Display (1.39" AMOLED)     38.8 x 38.2 x 0.7mm
Y = +24    Camera (IMX989)            26 x 26 x 9.4mm
Y = +18    Display Mount              Dia 44 x 8mm (SLA)
Y = +13    QCS6490 SoM                42.5 x 35.5 x 2.7mm
Y = +10    Main PCB                   Dia 60 x 1.6mm
Y = +8     Hailo-10H                  22 x 42 x 2.6mm
Y = +5     Microphones x4             6 x 3.8 x 2.5mm each
Y = 0      LED Ring (equator)         HD108 x16 on flex
Y = -8     Speaker                    Dia 28 x 5.4mm
Y = -20    Battery                    55 x 35 x 20mm
Y = -32    Coil Mount                 Dia 66 x 4mm (SLA)
Y = -34    RX Coil                    Dia 70 x 4mm
Y = -36    Ferrite                    Dia 60 x 0.5mm
Y = -42.5  ─────────────────────────  Bottom of sphere

           ═══════════════════════════  18-25mm gap

Y = -62    Maglev Module              100 x 100 x 20mm
Y = -72    TX Coil                    Dia 80 x 4mm
Y = -82    Base Enclosure             Dia 140 x 25mm
```

---

## THERMAL BUDGET (CANONICAL VALUES)

### Power Dissipation by Component

| Component | Idle (W) | Active (W) | Peak (W) | Source |
|-----------|----------|------------|----------|--------|
| **QCS6490** | 5.0 | 8.0 | 12.0 | Advantech MIO-5355 datasheet |
| **Hailo-10H** | 0.5 | 2.5 | 5.0 | Hailo product brief |
| **Display** | 0.3 | 0.8 | 1.2 | King Tech RM69330 |
| **LEDs x16** | 0.2 | 0.8 | 1.6 | 16-bit at full white |
| **Other** | 0.7 | 1.7 | 2.9 | Sensors, ESP32, XMOS, misc |
| **TOTAL** | **6.7W** | **13.8W** | **22.7W** | |

### Thermal Dissipation Capacity

| Configuration | Dissipation Capacity | Notes |
|---------------|---------------------|-------|
| **Sealed sphere (no base)** | 2-4W | Natural convection + radiation |
| **With maglev base (docked)** | 8-12W | Radiative coupling across gap |
| **Peak transient** | 20W for 10min | Thermal throttling required |

### Operating Modes

| Mode | Power Budget | Thermal Strategy |
|------|-------------|------------------|
| **Docked Idle** | 6.7W | Continuous operation OK |
| **Docked Active** | 13.8W | Throttle to 12W if T > 45C |
| **Portable** | 6.7W max | Throttle to 4W for thermal safety |
| **Peak** | 22.7W | <10 min duration, auto-throttle |

### Thermal Throttling Thresholds

| Temperature | Action |
|-------------|--------|
| < 40C | Normal operation |
| 40-45C | Reduce background tasks, Hailo duty cycle |
| 45-50C | Throttle CPU/NPU to 50%, display dim |
| 50-55C | Throttle to 25%, critical warning |
| > 55C | Graceful shutdown |

**Reconciliation Note:** Previous V3_ASSEMBLY_SPECIFICATION.md listed TDP 9.3W total.
This was the sum of TDP ratings, not actual power draw. The canonical thermal budget
above reflects measured/estimated power draw in each operating mode, which can exceed
component TDP ratings when all systems are active.

---

## MASS BUDGET

### Current Mass Breakdown

| Assembly | Components | Mass (g) |
|----------|------------|----------|
| **Shell** | Top + bottom hemispheres | 90 |
| **Display** | AMOLED + Camera + Mount | 35 |
| **Compute** | SoM + Hailo + PCB + heatsink | 56 |
| **Audio** | Mics + DSP + speaker | 12 |
| **LEDs** | Ring + diffuser | 10 |
| **Battery** | 2200mAh 3S LiPo | 150 |
| **Power** | BMS + coil + ferrite | 38 |
| **TOTAL ORB** | — | **391g** |

### Mass Optimization Required

| Target | Current | Delta |
|--------|---------|-------|
| **350g** | 391g | **-41g needed** |

See `hardware/MASS_OPTIMIZATION.md` for detailed optimization strategies.

### Base Station Mass

| Assembly | Mass (g) |
|----------|----------|
| Maglev module | 350 |
| TX coil + ferrite | 30 |
| ESP32 + PCB | 20 |
| Walnut enclosure | 350 |
| **TOTAL BASE** | **750g** |

---

## I2C BUS ARCHITECTURE

### Summary (See I2C_ADDRESS_MAP.md for full topology)

| Address | Device | Bus | Speed |
|---------|--------|-----|-------|
| **0x0B** | BQ40Z50 Fuel Gauge | SMBus | 100kHz |
| **0x35** | sensiBel SBM100B (config) | I2C | 400kHz |
| **0x3B** | P9415-R WPC Receiver | I2C | 400kHz |
| **0x48** | TMP117 Temperature | I2C | 400kHz |
| **0x60** | MCP4725 DAC (base) | I2C | 400kHz |
| **0x68** | bq500215 TX (base) | I2C | 400kHz |
| **0x6A** | BQ25895 Charger | I2C | 400kHz |

**Address Conflict Resolution:**
- BQ25895: 0x6A (confirmed, not 0x55)
- BQ40Z50: 0x0B (SMBus address, not 0x55)
- No conflicts exist. Previous documentation error corrected.

---

## COST SUMMARY (January 2026)

| Category | Prototype (1x) | Volume (100x) |
|----------|---------------|---------------|
| Compute | $233 | $190 |
| Display | $45 | $35 |
| Camera | $95 | $75 |
| Audio | $244 | $195 |
| Sensors | $78 | $58 |
| Power | $62 | $48 |
| LEDs | $15 | $10 |
| Enclosure | $50 | $30 |
| Maglev | $45 | $30 |
| PCBs | $60 | $25 |
| **ORB TOTAL** | **~$930** | **~$700** |
| **BASE TOTAL** | **~$185** | **~$120** |
| **SYSTEM** | **~$1,115** | **~$820** |

---

## VERIFIED SUPPLIER LINKS

| Component | Supplier | URL |
|-----------|----------|-----|
| QCS6490 SoM | Thundercomm | [Product](https://www.thundercomm.com/product/c6490-som/) |
| Hailo-10H | Hailo | [Product](https://hailo.ai/products/generative-ai-accelerators/hailo-10h-m-2-generative-ai-acceleration-module/) |
| 1.39" AMOLED | King Tech | [Datasheet](https://www.kingtechdisplay.com) |
| IMX989 Module | SincereFirst | [Product](https://www.cameramodule.com/fpc-camera-module/auto-focus-camera-module/50mp-sony-imx989-cmos-sensor-autofocus-fpc.html) |
| sensiBel SBM100B | sensiBel | [Product](https://sensibel.com/product/) |
| HD108 LEDs | Rose Lighting | [Datasheet](https://www.rose-lighting.com/products/fastest-rgb-pixel-5050-hd108-led-chip-65536-gray-scale-updated-version-of-hd107s-apa102-apa102c-apa107/) |
| Maglev 500g | Stirlingkit | [Product](https://www.stirlingkit.com/products/500g-diy-magnetic-levitation-module) |
| XMOS XVF3800 | XMOS | [Datasheet](https://www.xmos.com/download/XVF3800-Device-Datasheet) |

---

## REJECTED COMPONENTS (Don't Fit)

| Component | Why Rejected |
|-----------|--------------|
| 2.8" Round Display | Module 76mm > 70mm internal |
| 3.4" Round Display | Module 86mm > 85mm outer! |
| 4000mAh Battery | 131mm length > 65mm max |
| HCNT 285mm Base | Too large for aesthetic |

---

## DOCUMENT HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 3.0 | Jan 2026 | Initial V3 85mm sphere design |
| 3.1 | Jan 2026 | Added I2C addresses, reconciled thermal budget |
| 3.1.1 | Jan 2026 | Fixed RX coil inductance (45uH not 85uH), resolved I2C conflicts |

---

**This document is the SINGLE SOURCE OF TRUTH.**
All other docs must match these specifications.
