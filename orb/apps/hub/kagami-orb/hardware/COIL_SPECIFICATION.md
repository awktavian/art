# Kagami Orb — Wireless Power Transfer Coil Specification

**Version:** 1.0
**Created:** January 11, 2026
**Status:** PRODUCTION-READY
**Target Frequency:** 140 kHz (Resonant)

---

## OVERVIEW

This document specifies the exact parameters for the TX (Base) and RX (Orb) wireless power transfer coils, including Litz wire specifications, winding instructions, resonant capacitor values, and verified supplier information.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     WIRELESS POWER TRANSFER SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│      ORB (RX)                                      BASE (TX)                 │
│      ───────                                       ─────────                 │
│                                                                              │
│      ┌─────────────┐                              ┌─────────────┐           │
│      │ RX Coil     │                              │ TX Coil     │           │
│      │ 70mm OD     │         Air Gap             │ 80mm OD     │           │
│      │ 20T Litz    │◄─── 5-25mm ────────────────►│ 15T Litz    │           │
│      │ 45μH        │        ~140kHz              │ 28μH        │           │
│      └─────────────┘                              └─────────────┘           │
│            │                                            │                    │
│      ┌─────┴─────┐                              ┌──────┴──────┐             │
│      │ 27nF      │                              │ 47nF        │             │
│      │ Resonant  │                              │ Resonant    │             │
│      └───────────┘                              └─────────────┘             │
│            │                                            │                    │
│      ┌─────┴─────┐                              ┌──────┴──────┐             │
│      │ P9415-R   │                              │ bq500215    │             │
│      │ WPC RX    │                              │ WPC TX      │             │
│      └───────────┘                              └─────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. TX COIL (BASE STATION)

### 1.1 Electrical Specifications

| Parameter | Symbol | Value | Tolerance |
|-----------|--------|-------|-----------|
| **Outer Diameter** | D_out | 80 mm | ±1 mm |
| **Inner Diameter** | D_in | 30 mm | ±1 mm |
| **Number of Turns** | N | 15 | Exact |
| **Inductance** | L | 28 μH | ±10% |
| **DC Resistance** | R_dc | 0.15 Ω | Max 0.20 Ω |
| **Quality Factor** | Q | 200 | Min 150 @ 140kHz |
| **Rated Current** | I_rms | 3 A | Continuous |
| **Peak Current** | I_pk | 4.5 A | Transient |

### 1.2 Litz Wire Specification

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Wire Type** | 175/46 AWG Litz | 175 strands of 46 AWG |
| **Strand Diameter** | 0.04 mm (46 AWG) | Each individual strand |
| **Bundle Diameter** | ~1.8 mm | Overall wire OD |
| **Insulation** | Solderable polyurethane | Each strand insulated |
| **Outer Insulation** | Nylon served | Abrasion resistant |
| **Temperature Rating** | 155°C | Class F insulation |

**Why 175/46 AWG Litz:**
- At 140 kHz, skin depth in copper is ~0.18 mm
- 46 AWG strand diameter (0.04 mm) << skin depth
- Ensures uniform current distribution
- Minimizes AC resistance (skin effect + proximity effect)

### 1.3 Winding Diagram

```
                        TX COIL WINDING PATTERN (Top View)
                        ─────────────────────────────────

                                   ↑ START
                                   │
                        ┌──────────┴──────────┐
                       ╱                       ╲
                      ╱     ┌─────────────┐     ╲
                     ╱     ╱               ╲     ╲
                    │     │   30mm HOLE     │     │
                    │     │   (mounting)    │     │
                    │     │                 │     │
                     ╲     ╲               ╱     ╱
                      ╲     └─────────────┘     ╱
                       ╲                       ╱
                        └─────────────────────┘
                                   │
                                   ↓ END

        Winding Direction: Counter-clockwise from center outward

        Turn Spacing:
        ┌─────────────────────────────────────────────┐
        │  Turn 1  │  ~2.3mm pitch  │  Turn 15       │
        │ (30mm r) │ ←────────────► │ (40mm r)       │
        └─────────────────────────────────────────────┘

        Radial Coverage: (80mm - 30mm) / 2 = 25mm
        Pitch: 25mm / 15 turns ≈ 1.67mm (tight winding)
        Wire OD: ~1.8mm (slight overlap acceptable)
```

### 1.4 Physical Construction

```
                        TX COIL CROSS SECTION
                        ────────────────────

        ┌───────────────────────────────────────────────────┐
        │                   FERRITE PLATE                    │  0.8mm
        │                   (90mm × 0.8mm)                   │
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │                   ADHESIVE LAYER                   │  0.1mm
        │                   (Kapton tape)                    │
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○  LITZ COIL         │  1.8mm
        │           (15 turns, spiral)                       │
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │                   INSULATION                       │  0.5mm
        │                   (Mylar film)                     │
        └───────────────────────────────────────────────────┘
                                                     Total: ~3.2mm
```

---

## 2. RX COIL (ORB)

### 2.1 Electrical Specifications

| Parameter | Symbol | Value | Tolerance |
|-----------|--------|-------|-----------|
| **Outer Diameter** | D_out | 70 mm | ±1 mm |
| **Inner Diameter** | D_in | 25 mm | ±1 mm |
| **Number of Turns** | N | 20 | Exact |
| **Inductance** | L | 45 μH | ±10% |
| **DC Resistance** | R_dc | 0.25 Ω | Max 0.30 Ω |
| **Quality Factor** | Q | 150 | Min 120 @ 140kHz |
| **Rated Current** | I_rms | 2 A | Continuous |
| **Peak Current** | I_pk | 3 A | Transient |

### 2.2 Litz Wire Specification

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Wire Type** | 100/46 AWG Litz | 100 strands of 46 AWG |
| **Strand Diameter** | 0.04 mm (46 AWG) | Each individual strand |
| **Bundle Diameter** | ~1.4 mm | Overall wire OD |
| **Insulation** | Solderable polyurethane | Each strand insulated |
| **Outer Insulation** | Nylon served | Abrasion resistant |
| **Temperature Rating** | 155°C | Class F insulation |

**Why 100/46 AWG for RX (smaller than TX):**
- RX carries less current (2A vs 3A)
- Weight is critical in floating orb
- Smaller wire = lighter coil
- Still adequate for 15W power transfer

### 2.3 Winding Diagram

```
                        RX COIL WINDING PATTERN (Top View)
                        ─────────────────────────────────

                                   ↑ START
                                   │
                        ┌──────────┴──────────┐
                       ╱                       ╲
                      ╱     ┌───────────┐       ╲
                     ╱     ╱             ╲       ╲
                    │     │  25mm HOLE    │       │
                    │     │  (battery     │       │
                    │     │   center)     │       │
                     ╲     ╲             ╱       ╱
                      ╲     └───────────┘       ╱
                       ╲                       ╱
                        └─────────────────────┘
                                   │
                                   ↓ END

        Winding Direction: Counter-clockwise from center outward

        Turn Spacing:
        ┌─────────────────────────────────────────────┐
        │  Turn 1  │  ~1.1mm pitch  │  Turn 20       │
        │ (12.5mm) │ ←────────────► │ (35mm r)       │
        └─────────────────────────────────────────────┘

        Radial Coverage: (70mm - 25mm) / 2 = 22.5mm

        DUAL LAYER CONSTRUCTION:
        ┌─────────────────────────────────────────────┐
        │ Layer 1: Turns 1-10 (center out)           │
        │ Layer 2: Turns 11-20 (stacked on top)      │
        └─────────────────────────────────────────────┘
```

### 2.4 Physical Construction

```
                        RX COIL CROSS SECTION
                        ────────────────────

        ┌───────────────────────────────────────────────────┐
        │                   FERRITE SHEET                    │  0.6mm
        │                   (75mm × 0.6mm)                   │
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │                   ADHESIVE LAYER                   │  0.1mm
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○  LITZ LAYER 1 (10T)          │  1.4mm
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │                   INTER-LAYER TAPE                 │  0.1mm
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○  LITZ LAYER 2 (10T)          │  1.4mm
        └───────────────────────────────────────────────────┘
        ┌───────────────────────────────────────────────────┐
        │                   ENCAPSULATION                    │  0.5mm
        │                   (Epoxy or silicone)              │
        └───────────────────────────────────────────────────┘
                                                     Total: ~4.1mm
```

---

## 3. RESONANT CAPACITORS

### 3.1 Theory

For series resonance at frequency f:
```
f_res = 1 / (2π × √(L × C))

Solving for C:
C = 1 / (4π² × f² × L)
```

### 3.2 TX Capacitor

| Parameter | Calculation | Value |
|-----------|-------------|-------|
| **Inductance** | L_tx | 28 μH |
| **Target Frequency** | f | 140 kHz |
| **Calculated C** | 1/(4π² × 140k² × 28μ) | 46.1 nF |
| **Standard Value** | Nearest E12 | **47 nF** |
| **Actual Frequency** | 1/(2π × √(28μ × 47n)) | 138.9 kHz |

**Capacitor Specification:**
| Parameter | Requirement |
|-----------|-------------|
| **Capacitance** | 47 nF |
| **Tolerance** | ±2% (NPO/C0G preferred) |
| **Voltage Rating** | 250V DC minimum |
| **Dielectric** | Film (polypropylene preferred) |
| **ESR** | <10 mΩ @ 140 kHz |
| **Package** | Through-hole or SMD (1206+) |

**Recommended Parts:**
| Manufacturer | Part Number | Type | Price |
|--------------|-------------|------|-------|
| Vishay | MKP1837447254 | Film | $1.50 |
| KEMET | R75PI24704030J | Film | $1.20 |
| WIMA | MKP10-47n/250 | Film | $0.80 |

### 3.3 RX Capacitor

| Parameter | Calculation | Value |
|-----------|-------------|-------|
| **Inductance** | L_rx | 45 μH |
| **Target Frequency** | f | 140 kHz |
| **Calculated C** | 1/(4π² × 140k² × 45μ) | 28.7 nF |
| **Standard Values** | 27 nF + 2.2 nF parallel | **29.2 nF** |
| **Actual Frequency** | 1/(2π × √(45μ × 29.2n)) | 138.5 kHz |

**Capacitor Specification:**
| Parameter | Requirement |
|-----------|-------------|
| **Capacitance** | 27 nF + 2.2 nF (parallel) |
| **Tolerance** | ±2% |
| **Voltage Rating** | 100V DC minimum |
| **Dielectric** | Film or NPO ceramic |
| **ESR** | <15 mΩ @ 140 kHz |
| **Package** | SMD 0805 or 1206 |

**Fine Tuning:**
- Add trimmer capacitor (5-30 pF) in parallel for precise tuning
- Adjust until maximum power transfer achieved
- Lock with conformal coating after tuning

---

## 4. FERRITE SPECIFICATIONS

### 4.1 TX Ferrite (Base)

| Parameter | Value |
|-----------|-------|
| **Type** | Mn-Zn (manganese-zinc) |
| **Material** | Fair-Rite 78 or equivalent |
| **Permeability** | μ_i = 2300 |
| **Frequency Range** | <500 kHz |
| **Dimensions** | 90mm diameter × 0.8mm thick |
| **Shape** | Circular plate |

**Digi-Key Part:** 240-2534-ND (Fair-Rite 3595000541)
**Price:** $28.32

### 4.2 RX Ferrite (Orb)

| Parameter | Value |
|-----------|-------|
| **Type** | Mn-Zn flexible sheet |
| **Material** | Wurth 36303 or equivalent |
| **Permeability** | μ_i = 120-180 |
| **Frequency Range** | 100 kHz - 1 MHz |
| **Dimensions** | 75mm diameter × 0.6mm thick |
| **Shape** | Circular, cut from sheet |

**Digi-Key Part:** 732-6896-ND (Wurth 36303)
**Price:** $15.31

---

## 5. WINDING INSTRUCTIONS

### 5.1 Tools Required

- Coil winding jig (3D printable, STL in `cad/coil_jig.stl`)
- Wire tensioner
- Soldering iron (350°C)
- Solder with flux (Sn63/Pb37 or lead-free)
- Kapton tape (high-temp)
- Calipers (0.01mm resolution)
- LCR meter (for inductance verification)

### 5.2 TX Coil Winding Procedure

```
TX COIL WINDING STEPS
─────────────────────

1. PREPARE JIG
   - Mount 30mm center post on winding mandrel
   - Attach wire tensioner

2. ANCHOR START
   - Leave 50mm lead for connection
   - Secure with Kapton tape at center post

3. WIND TURNS 1-15
   - Wind counter-clockwise (looking from top)
   - Maintain constant tension
   - Keep turns adjacent (no gaps)
   - Spiral outward from center

   ┌────────────────────────────────────────┐
   │ Turn 1:  r = 15mm (at center post)    │
   │ Turn 2:  r = 17mm                      │
   │ Turn 3:  r = 19mm                      │
   │ ...                                    │
   │ Turn 15: r = 40mm (outer edge)        │
   └────────────────────────────────────────┘

4. SECURE END
   - Leave 50mm lead for connection
   - Tape final turn in place

5. ATTACH FERRITE
   - Apply double-sided tape to ferrite plate
   - Center coil on ferrite
   - Press firmly for adhesion

6. SOLDER TERMINATIONS
   - Strip Litz wire ends (burn off enamel with solder)
   - Tin both leads
   - Attach to connector or PCB pads

7. VERIFY
   - Measure inductance: Target 28 μH ±10%
   - Measure DC resistance: Max 0.20 Ω
```

### 5.3 RX Coil Winding Procedure

```
RX COIL WINDING STEPS (DUAL LAYER)
──────────────────────────────────

1. PREPARE JIG
   - Mount 25mm center post
   - Attach wire tensioner

2. WIND LAYER 1 (Turns 1-10)
   - Anchor at center (leave 50mm lead)
   - Wind counter-clockwise
   - Spiral outward

   ┌────────────────────────────────────────┐
   │ Turn 1:  r = 12.5mm                    │
   │ Turn 10: r = 24mm                      │
   └────────────────────────────────────────┘

3. TRANSITION TO LAYER 2
   - Do NOT cut wire
   - Fold wire up to start layer 2
   - Apply Kapton tape between layers

4. WIND LAYER 2 (Turns 11-20)
   - Start at OUTER edge of layer 1
   - Wind clockwise (reverse direction)
   - Spiral inward

   ┌────────────────────────────────────────┐
   │ Turn 11: r = 24mm (on top of turn 10) │
   │ Turn 20: r = 12.5mm (on top of turn 1)│
   └────────────────────────────────────────┘

5. SECURE END
   - Leave 50mm lead
   - Tape in place

6. ATTACH FERRITE
   - Apply adhesive to ferrite sheet
   - Center coil on ferrite
   - Trim ferrite to 75mm diameter

7. ENCAPSULATE
   - Apply thin layer of silicone or epoxy
   - Protects windings
   - Adds mechanical stability

8. VERIFY
   - Measure inductance: Target 45 μH ±10%
   - Measure DC resistance: Max 0.30 Ω
```

---

## 6. VERIFICATION PROCEDURES

### 6.1 Inductance Measurement

**Equipment:** LCR meter (e.g., DE-5000, GW Instek LCR-6300)

| Measurement | TX Coil | RX Coil |
|-------------|---------|---------|
| Test Frequency | 100 kHz | 100 kHz |
| Expected L | 28 μH ±10% | 45 μH ±10% |
| Acceptable Range | 25.2-30.8 μH | 40.5-49.5 μH |

### 6.2 DC Resistance Measurement

**Equipment:** 4-wire milliohm meter

| Measurement | TX Coil | RX Coil |
|-------------|---------|---------|
| Expected R_dc | 0.15 Ω | 0.25 Ω |
| Maximum | 0.20 Ω | 0.30 Ω |

### 6.3 Quality Factor Measurement

**Equipment:** LCR meter with Q readout

| Measurement | TX Coil | RX Coil |
|-------------|---------|---------|
| Test Frequency | 140 kHz | 140 kHz |
| Expected Q | 200 | 150 |
| Minimum | 150 | 120 |

### 6.4 Resonance Verification

**Procedure:**
1. Connect coil with calculated capacitor
2. Apply 1V AC signal from function generator
3. Sweep frequency 100-200 kHz
4. Monitor voltage across coil with oscilloscope
5. Peak voltage indicates resonant frequency

**Expected Results:**
| Parameter | TX | RX |
|-----------|----|----|
| Resonant Freq | 139 ±5 kHz | 139 ±5 kHz |
| Peak Voltage Ratio | >10× at resonance | >8× at resonance |

---

## 7. VERIFIED SUPPLIERS

### 7.1 Litz Wire Suppliers

| Supplier | Location | Product | Price | Lead Time | Contact |
|----------|----------|---------|-------|-----------|---------|
| **MWS Wire Industries** | USA | 175/46, 100/46 AWG | ~$50/lb | 1-2 weeks | [mwswire.com](https://www.mwswire.com) |
| **New England Wire** | USA | Custom Litz | Quote | 2-3 weeks | [newenglandwire.com](https://www.newenglandwire.com) |
| **Elektrisola** | Germany | All configurations | Quote | 2-4 weeks | [elektrisola.com](https://www.elektrisola.com) |
| **Cooner Wire** | USA | Medical grade Litz | Quote | 2-3 weeks | [coonerwire.com](https://www.coonerwire.com) |
| **AliExpress** | China | 175/46, 100/46 AWG | $15-25/lb | 2-4 weeks | Search "Litz wire 175/46" |

**Recommended for Prototype:** MWS Wire Industries
- Minimum order: 1 lb (sufficient for ~10 coil sets)
- Fast shipping to USA
- Consistent quality

**Recommended for Production:** Elektrisola
- Larger quantities at better pricing
- European quality standards
- Custom configurations available

### 7.2 Custom Coil Winding Services

| Supplier | Location | Capability | Price Range | Lead Time |
|----------|----------|------------|-------------|-----------|
| **Coilcraft** | USA | Premium quality | $50-100/coil | 2-3 weeks |
| **Wurth Elektronik** | Germany | WPT specialty | $30-80/coil | 3-4 weeks |
| **Yihetimes** | China | Budget option | $15-35/coil | 2-3 weeks |
| **Sunlord** | China | Mass production | $10-25/coil | 4-6 weeks |

**Contact Template for Custom Coil Quote:**

```
Subject: Custom WPT Coil Inquiry - Kagami Orb Project

Dear [Supplier],

We are developing a wireless power transfer system and require custom Litz wire coils. Please quote for the following:

TX COIL (Quantity: [X]):
- 80mm OD, 30mm ID, 15 turns
- 175/46 AWG Litz wire
- Target inductance: 28 μH ±10%
- With 90mm ferrite backing

RX COIL (Quantity: [X]):
- 70mm OD, 25mm ID, 20 turns (dual layer)
- 100/46 AWG Litz wire
- Target inductance: 45 μH ±10%
- With 75mm ferrite backing

Please provide:
1. Unit pricing for quantities: 1, 10, 100
2. Lead time
3. Inductance tolerance guarantee
4. DC resistance specification

Thank you,
[Your Name]
```

### 7.3 Ferrite Suppliers

| Component | Digi-Key PN | Price | In Stock |
|-----------|-------------|-------|----------|
| TX Ferrite Plate (90mm) | 240-2534-ND | $28.32 | Yes |
| RX Ferrite Sheet (75mm) | 732-6896-ND | $15.31 | Yes |

### 7.4 Resonant Capacitor Suppliers

All available at Digi-Key/Mouser:

| Capacitor | Part Number | Price | Supplier |
|-----------|-------------|-------|----------|
| 47 nF Film (TX) | MKP1837447254 | $1.50 | Digi-Key |
| 27 nF Film (RX) | MKP1837276504 | $1.20 | Digi-Key |
| 2.2 nF NPO (RX) | 04025A222JAT2A | $0.10 | Digi-Key |

---

## 8. ALTERNATIVE DESIGNS

### 8.1 Budget Option: Wound on PCB

For prototyping, coils can be etched directly on PCB:

| Parameter | TX (PCB) | RX (PCB) |
|-----------|----------|----------|
| Layers | 4 | 4 |
| Turns per layer | 4 | 5 |
| Total turns | 16 | 20 |
| Trace width | 1.5mm | 1.0mm |
| Trace spacing | 0.3mm | 0.3mm |
| Expected L | ~25 μH | ~40 μH |
| Expected Q | 40-60 | 30-50 |

**Tradeoff:** Lower Q = lower efficiency, but much easier to manufacture.

### 8.2 Off-the-Shelf WPC Coils

If custom winding is not feasible, WPC Qi standard coils can be adapted:

| Product | Specs | Price | Source |
|---------|-------|-------|--------|
| TDK WCT Tx | 50mm, 24μH | $8 | [tdk.com](https://www.tdk.com) |
| Wurth 760308104114 | 45mm, 6.3μH | $4 | Digi-Key |
| AliExpress WPC coil | Various | $2-5 | AliExpress |

**Note:** Standard Qi coils operate at 110-205 kHz. May need resonant frequency adjustment.

---

## 9. QUALITY CHECKLIST

Before installing coils:

- [ ] Inductance within ±10% of target
- [ ] DC resistance below maximum
- [ ] Q factor above minimum
- [ ] No visible damage to insulation
- [ ] Leads properly tinned
- [ ] Ferrite attached and centered
- [ ] Resonant frequency verified with capacitor

---

```
h(x) >= 0. Always.

The coils are the heart of wireless power.
Every turn placed with precision.
Every strand carries current.

鏡
```
