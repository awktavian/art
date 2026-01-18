# Kagami Orb V3.1 — VERIFIED SPECIFICATIONS

**SINGLE SOURCE OF TRUTH**  
**Last Updated:** January 2026  
**Verification Method:** Manufacturer datasheets + web research

---

## 🔴 DESIGN CONSTRAINTS

| Parameter | Value | Source |
|-----------|-------|--------|
| **Outer diameter** | 85mm | Design target |
| **Shell thickness** | 7.5mm | Structural |
| **Internal diameter** | 70mm | 85 - 15 = 70mm |
| **Max component** | ~65mm | 2.5mm clearance |
| **Levitation gap** | 18-25mm | Stirlingkit spec |
| **Max orb mass** | 350g | 500g - 150g margin |

---

## ✅ VERIFIED COMPONENTS

### Compute

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **QCS6490 SoM** | 42.5 × 35.5 × 2.7mm | ~25g | [Thundercomm](https://www.thundercomm.com/product/c6490-som/) |
| **Hailo-10H M.2** | 22 × 42 × 2.63mm | ~8g | [Hailo](https://hailo.ai/products/generative-ai-accelerators/hailo-10h-m-2-generative-ai-acceleration-module/) |
| **ESP32-S3-WROOM-1** | 25.5 × 18 × 3.1mm | ~3g | Espressif datasheet |

### Display

| Component | Dimensions | Active Area | Source |
|-----------|------------|-------------|--------|
| **1.39" AMOLED** | 38.83 × 38.21 × 0.68mm | Ø35.41mm | [King Tech Display](https://www.kingtechdisplay.com) |
| Resolution | 454 × 454 | — | RM69330 driver |
| Interface | MIPI DSI | — | — |

### Camera

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **IMX989 Module** | 26 × 26 × 9.4mm | ~15g | [SincereFirst](https://www.cameramodule.com/fpc-camera-module/auto-focus-camera-module/50mp-sony-imx989-cmos-sensor-autofocus-fpc.html) |
| Resolution | 50.3MP | — | Sony |
| Sensor | 1/0.98" type | — | 16.384mm diagonal |

### Audio

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **sensiBel SBM100B** | 6.0 × 3.8 × 2.47mm | <0.5g | [sensiBel](https://sensibel.com/product/) |
| **XMOS XVF3800** | 7 × 7 × 0.9mm (QFN-60) | <1g | XMOS datasheet |
| **28mm Speaker** | Ø28 × 5.4mm | ~5g | Yueda spec |

### LEDs

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **HD108 5050** | 5.1 × 5.0 × 1.6mm | <0.1g | [Rose Lighting](https://www.rose-lighting.com/products/fastest-rgb-pixel-5050-hd108-led-chip-65536-gray-scale-updated-version-of-hd107s-apa102-apa102c-apa107/) |
| Color depth | 16-bit | — | 65,536 levels/ch |
| Quantity | 16 LEDs | ~1g total | Equator ring |

### Power

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **Battery 2200mAh 3S** | 55 × 35 × 20mm | ~150g | Verified fit analysis |
| Energy | 24Wh (11.1V) | — | — |
| Runtime | 4-6 hours | — | At 4-6W average |
| **RX Coil** | Ø70 × 4mm | ~18g | Custom Litz wire |
| **Ferrite** | Ø60 × 0.5mm | ~12g | Mn-Zn shield |

### Maglev Base

| Component | Dimensions | Weight | Source |
|-----------|------------|--------|--------|
| **Stirlingkit 500g Module** | 100 × 100 × 20mm | ~350g | [Stirlingkit](https://www.stirlingkit.com/products/500g-diy-magnetic-levitation-module) |
| Float height | 18-25mm | — | Varies with load |
| Max capacity | 500g | — | At 18mm gap |
| **TX Coil** | Ø70 × 4mm | ~15g | Custom Litz wire |
| **Base Enclosure** | Ø140 × 25mm | ~350g | CNC walnut |

---

## 📐 ASSEMBLY STACK (Y coordinates in mm)

```
Y = +42.5  ─────────────────────────  Top of sphere
Y = +30    Display (1.39" AMOLED)     38.8 × 38.2 × 0.7mm
Y = +24    Camera (IMX989)            26 × 26 × 9.4mm
Y = +18    Display Mount              Ø44 × 8mm (SLA)
Y = +13    QCS6490 SoM                42.5 × 35.5 × 2.7mm
Y = +10    Main PCB                   Ø60 × 1.6mm
Y = +8     Hailo-10H                  22 × 42 × 2.6mm
Y = +5     Microphones ×4             6 × 3.8 × 2.5mm each
Y = 0      LED Ring (equator)         HD108 ×16 on flex
Y = -8     Speaker                    Ø28 × 5.4mm
Y = -20    Battery                    55 × 35 × 20mm
Y = -32    Coil Mount                 Ø66 × 4mm (SLA)
Y = -34    RX Coil                    Ø70 × 4mm
Y = -36    Ferrite                    Ø60 × 0.5mm
Y = -42.5  ─────────────────────────  Bottom of sphere

           ═══════════════════════════  18-25mm gap

Y = -62    Maglev Module              100 × 100 × 20mm
Y = -72    TX Coil                    Ø70 × 4mm
Y = -82    Base Enclosure             Ø140 × 25mm
```

---

## ⚖️ MASS BUDGET

| Assembly | Components | Mass |
|----------|------------|------|
| **Shell** | Top + bottom hemispheres | 90g |
| **Display** | AMOLED + Camera + Mount | 35g |
| **Compute** | SoM + Hailo + PCB + heatsink | 56g |
| **Audio** | Mics + DSP + speaker | 12g |
| **LEDs** | Ring + diffuser | 10g |
| **Battery** | 2200mAh 3S LiPo | 150g |
| **Power** | BMS + coil + ferrite | 38g |
| **TOTAL ORB** | — | **391g** |

⚠️ **Exceeds 350g target by 41g** — optimize shell/mount weight

| Base Assembly | Mass |
|---------------|------|
| Maglev module | 350g |
| TX coil + ferrite | 30g |
| ESP32 + PCB | 20g |
| Walnut enclosure | 350g |
| **TOTAL BASE** | **750g** |

---

## 🌡️ THERMAL BUDGET

| Component | Idle | Active | Peak |
|-----------|------|--------|------|
| QCS6490 | 5.0W | 8.0W | 12.0W |
| Hailo-10H | 0.5W | 2.5W | 5.0W |
| Display | 0.3W | 0.8W | 1.2W |
| LEDs | 0.2W | 0.8W | 1.6W |
| Other | 0.7W | 1.7W | 2.9W |
| **TOTAL** | **6.7W** | **13.8W** | **22.7W** |

| Mode | Generation | Dissipation | Strategy |
|------|------------|-------------|----------|
| Docked idle | 6.7W | 8-12W | ✅ OK |
| Docked active | 13.8W | 8-12W | ⚠️ Throttle to 12W |
| Portable | 6.7W | 2-4W | ⚠️ Throttle to 4W |

---

## 💰 COST SUMMARY (January 2026)

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

## 🔗 VERIFIED SUPPLIER LINKS

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

## ❌ REJECTED COMPONENTS (Don't Fit)

| Component | Why Rejected |
|-----------|--------------|
| 2.8" Round Display | Module 76mm > 70mm internal |
| 3.4" Round Display | Module 86mm > 85mm outer! |
| 4000mAh Battery | 131mm length > 65mm max |
| HCNT 285mm Base | Too large for aesthetic |

---

**This document is the SINGLE SOURCE OF TRUTH.**  
All other docs must match these specifications.
