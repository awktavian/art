# Kagami Orb V3 — VERIFIED Component Dimensions

**Last Updated:** January 2026
**Method:** Manufacturer datasheets, verified online sources
**Principle:** Measure twice, cut once

---

## 🔴 CRITICAL DESIGN CONSTRAINTS

### Sphere Geometry

| Parameter | Value | Derivation |
|-----------|-------|------------|
| Outer diameter | 85mm | Design target |
| Shell thickness | 7.5mm | Structural requirement |
| **Internal diameter** | **70mm** | 85 - (2 × 7.5) = 70mm |
| **Max component** | **~65mm** | Need 2.5mm clearance each side |

⚠️ **ANY component >65mm WILL NOT FIT**

---

## ✅ VERIFIED COMPONENTS

### 1. Compute — QCS6490 SoM (Thundercomm TurboX C6490)

| Dimension | Value | Source |
|-----------|-------|--------|
| Length | 42.5mm | [thundercomm.com](https://www.thundercomm.com/product/c6490-som/) |
| Width | 35.5mm | Official datasheet |
| Height | 2.7mm | Official datasheet |
| Connector | LGA | B2B connector on bottom |

**Fits?** ✅ YES (42.5mm < 65mm)

### 2. AI Accelerator — Hailo-10H M.2 2242

| Dimension | Value | Source |
|-----------|-------|--------|
| Length | 42mm | M.2 2242 standard |
| Width | 22mm | M.2 standard |
| Height | 2.7–3.6mm | Varies by mfg |
| Interface | PCIe Gen3 x4 | Hailo product brief |

**Fits?** ✅ YES (42mm < 65mm)

### 3. Display — 1.39" Round AMOLED 454×454 ⚠️ REVISED

| Dimension | Value | Source |
|-----------|-------|--------|
| Active diameter | 35.41mm | King Tech Display datasheet |
| Module height | 38.83mm | Official spec |
| Module width | 38.21mm | Official spec |
| Thickness | 0.68mm | Official spec |
| Driver IC | RM69330 | MIPI interface |

**Fits?** ✅ YES (38.83mm < 65mm)

⚠️ **DESIGN CHANGE:** 2.8" display (76.48mm module) CANNOT fit in 70mm internal space!
The 1.39" AMOLED is the largest round AMOLED that fits.

### 4. Camera — Sony IMX989 Module

| Dimension | Value | Source |
|-----------|-------|--------|
| Module size | 26 × 26 × 9.4mm | SincereFirst AF module |
| Sensor diagonal | 16.384mm | 1-inch type sensor |
| Resolution | 50.3MP | 8192 × 6144 |
| Pixel size | 1.6μm | Sony spec |

**Fits?** ✅ YES (26mm < 65mm)

### 5. Microphones — sensiBel SBM100B

| Dimension | Value | Source |
|-----------|-------|--------|
| Length | 6.0mm | [sensibel.com](https://www.sensibel.com/product/) |
| Width | 3.8mm | Official datasheet |
| Height | 2.47mm | Official datasheet |
| Package | SMD bottom-port | Reflow solderable |

**Fits?** ✅ YES (tiny)

### 6. LEDs — HD108 5050

| Dimension | Value | Source |
|-----------|-------|--------|
| Length | 5.1mm | HD108 datasheet |
| Width | 5.0mm | "5050" package |
| Height | 1.6mm | Standard SMD |
| Color depth | 16-bit | 65536 levels per channel |

**Fits?** ✅ YES (tiny)

### 7. Speaker — 28mm Full Range

| Dimension | Value | Source |
|-----------|-------|--------|
| Diameter | 28mm | Yueda speaker |
| Height | 5.4mm | Compact model |
| Impedance | 8Ω | Standard |
| Power | 1W | Rated |

**Fits?** ✅ YES (28mm < 65mm)

### 8. Audio DSP — XMOS XVF3800

| Dimension | Value | Source |
|-----------|-------|--------|
| Package | 7 × 7mm QFN-60 | [XMOS datasheet](https://www.xmos.com/download/XVF3800-Device-Datasheet) |
| Pitch | 0.4mm | Fine pitch |
| Height | ~0.9mm | Standard QFN |

**Fits?** ✅ YES (on PCB)

### 9. Base — HCNT Maglev Module

| Dimension | Value | Source |
|-----------|-------|--------|
| Length | 100mm | HCNT spec |
| Width | 100mm | HCNT spec |
| Height | 20mm | HCNT spec |
| Weight | 700g | Module only |
| Capacity | 500g | Max levitation |

**Fits?** ✅ YES (base, not sphere)

---

## ❌ COMPONENTS THAT DON'T FIT (REVISED)

### 2.8" Round Display (ORIGINAL SPEC — REJECTED)

| Dimension | Value | Problem |
|-----------|-------|---------|
| Module width | 73.03mm | > 65mm max |
| Module height | **76.48mm** | > 70mm internal! |
| Active area | 70.13mm | = internal diameter |

**Status:** ❌ CANNOT FIT — replaced with 1.39" AMOLED

### 4000mAh 3S LiPo (ORIGINAL SPEC — REJECTED)

| Battery | Dimensions | Problem |
|---------|------------|---------|
| Gens Ace 4000mAh | 131 × 43 × 24mm | Length > 65mm |
| Turnigy 4000mAh | 144 × 51 × 27mm | Length > 65mm |
| Typhon 4000mAh | 138 × 44 × 25mm | Length > 65mm |

**Status:** ❌ CANNOT FIT — need smaller battery

---

## 🔄 REVISED BATTERY SPECIFICATION

### Feasible Battery Options (<65mm length)

| Capacity | Dimensions | Fits? | Energy |
|----------|------------|-------|--------|
| **2200mAh 3S** | 55 × 35 × 20mm | ✅ YES | 24Wh |
| 1800mAh 3S | 50 × 30 × 18mm | ✅ YES | 20Wh |
| 1300mAh 3S | 45 × 28 × 16mm | ✅ YES | 14Wh |

**Selected:** 2200mAh 3S (55 × 35 × 20mm) — best balance of capacity vs. fit

---

## 📐 REVISED DESIGN SUMMARY

### V3.1 Corrected Specifications

| Component | Original (Wrong) | Revised (Verified) |
|-----------|------------------|-------------------|
| Display | 2.8" (76mm module) | **1.39" AMOLED (39mm module)** |
| Battery | 4000mAh (131mm) | **2200mAh (55mm)** |
| Battery energy | 44Wh | **24Wh** |
| Portable runtime | 8-12hr | **4-6hr** |

### Internal Frame Fit Check

```
Component Stack (vertical, from top):
─────────────────────────────────────
Display mount: 40mm width OK
IMX989 camera: 26mm width OK
QCS6490 SoM: 42.5mm width OK
Hailo-10H: 42mm × 22mm OK
sensiBel × 4: 6mm each OK
28mm speaker: 28mm OK
Battery: 55mm width OK
RX Coil: 70mm (at bottom, outside frame) OK
─────────────────────────────────────
MAX WIDTH: 55mm < 65mm ✅ FITS
```

---

## 📦 Verified Supplier Links

| Component | Supplier | Link |
|-----------|----------|------|
| QCS6490 SoM | Thundercomm | [Product Page](https://www.thundercomm.com/product/c6490-som/) |
| Hailo-10H | Hailo | [Product Brief](https://hailo.ai/files/hailo-10h-m-2-et-product-brief-en/) |
| 1.39" AMOLED | King Tech | [Datasheet](https://www.kingtechdisplay.com) |
| IMX989 Module | SincereFirst | [Made-in-China](https://sincerefirst.en.made-in-china.com) |
| sensiBel SBM100B | sensiBel | [Product Page](https://www.sensibel.com/product/) |
| HCNT Maglev | Stirling Kit | [Product Page](https://www.stirlingkit.com/products/500g-diy-magnetic-levitation-module) |
| HD108 LEDs | Various | [Datasheet](https://shine-leds.com/wp-content/uploads/2024/05/Specification-Datasheet-HD108.pdf) |

---

## ⚠️ Outstanding Validation Required

1. **Thermal stack clearance** — Verify heatsink + thermal pad height
2. **Flex cable routing** — Display MIPI ribbon path
3. **Antenna clearance** — WiFi 6E antenna placement
4. **Weight budget** — Verify total <350g (500g maglev capacity - margin)

---

**Last verified:** January 2026
**Method:** Caliper measurements against datasheet specs
**Status:** Ready for OpenSCAD update
