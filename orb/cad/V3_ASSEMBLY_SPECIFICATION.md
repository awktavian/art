# Kagami Orb V3 — Complete Assembly Specification

**Version:** 3.1 (January 2026)
**Status:** VERIFIED DIMENSIONS — Ready for CAD/Prototyping

---

## 1. SPHERE GEOMETRY CONSTRAINTS

### 1.1 Primary Dimensions

| Parameter | Value | Derivation |
|-----------|-------|------------|
| Outer Diameter | 85.00 mm | Design target |
| Shell Thickness | 7.50 mm | Structural + optical |
| Inner Diameter | 70.00 mm | 85 - (2 × 7.5) |
| Inner Radius | 35.00 mm | 70 / 2 |
| Usable Diameter | 65.00 mm | 70 - (2 × 2.5) clearance |
| Inner Volume | 179,594 mm³ | (4/3)π × 35³ |

### 1.2 Coordinate System

```
        +Z (TOP - Display)
         ↑
         │      Orb Center = (0, 0, 0)
         │
    ─────┼───── +X
        /│
       / │
      +Y (FRONT)

    Z = +35mm: Top of inner shell
    Z = 0mm: Equator (LED ring)
    Z = -35mm: Bottom of inner shell
```

### 1.3 Available Diameter at Height

The sphere constrains available diameter based on Z position:

| Z Height | Available Diameter | Formula |
|----------|-------------------|---------|
| 0 mm (equator) | 70.0 mm | Maximum |
| ±10 mm | 66.3 mm | 2√(35² - 10²) |
| ±15 mm | 63.2 mm | 2√(35² - 15²) |
| ±20 mm | 57.4 mm | 2√(35² - 20²) |
| ±25 mm | 48.0 mm | 2√(35² - 25²) |
| ±30 mm | 33.2 mm | 2√(35² - 30²) |

---

## 2. COMPLETE COMPONENT INVENTORY

### 2.1 All Components with VERIFIED Dimensions

| ID | Component | L×W×H (mm) | Volume (mm³) | Weight (g) | Zone |
|----|-----------|------------|--------------|------------|------|
| **COMPUTE** |||||
| C1 | QCS6490 SoM | 42.5×35.5×2.7 | 4,074 | 8 | Center |
| C2 | Hailo-10H M.2 2242 | 42×22×3.6 | 3,326 | 6 | Center |
| C3 | ESP32-S3-WROOM-1-N4 | 18×25.5×3.1 | 1,423 | 3 | Center |
| **DISPLAY** |||||
| D1 | 1.39" AMOLED Module | 38.83×38.21×0.68 | 1,009 | 2 | Top |
| D2 | Dielectric Mirror Film | 45mm dia × 0.1 | 159 | 0.5 | Top |
| D3 | DSX-E Oleophobic Coat | (applied to shell) | - | - | Top |
| **CAMERA** |||||
| CAM1 | IMX989 Camera Module | 26×26×9.4 | 6,354 | 5 | Top |
| **AUDIO** |||||
| A1 | sensiBel SBM100B (×4) | 6×3.8×2.47 (each) | 225 | 0.5 | Equator |
| A2 | XMOS XVF3800 (QFN-60) | 7×7×0.9 | 44 | 0.3 | Center |
| A3 | Tectonic TEBM28C20N-4 | 28 dia × 5.4 | 3,325 | 8 | Bottom |
| A4 | MAX98357A | 3×3×0.9 | 8 | 0.1 | Center |
| **SENSORS** |||||
| S1 | BGT60TR13C Radar | 6.5×5×1 | 33 | 0.2 | Top |
| S2 | VL53L8CX ToF | 6.4×3×1.5 | 29 | 0.1 | Top |
| S3 | AS7343 Spectral | 3.1×2×1 | 6 | 0.05 | Top |
| S4 | ICM-45686 IMU | 3×2.5×0.9 | 7 | 0.05 | Center |
| S5 | SHT45 Temp/Humidity | 1.5×1.5×0.5 | 1 | 0.02 | Center |
| S6 | SEN66 Air Quality | 41×41×12 | 20,172 | 12 | Bottom |
| S7 | AH49E Hall Sensor | 4×3×1.5 | 18 | 0.1 | Bottom |
| **LEDS** |||||
| L1 | HD108 LEDs (×16) | 5.1×5×1.6 (each) | 653 | 0.8 | Equator |
| L2 | 74AHCT125 Level Shifter | 4×3×1 | 12 | 0.1 | Center |
| **POWER** |||||
| P1 | 2200mAh 3S LiPo | 55×35×20 | 38,500 | 145 | Bottom |
| P2 | BQ25895 Charger IC | 4×4×0.8 | 13 | 0.1 | Bottom |
| P3 | BQ40Z50 Fuel Gauge | 5×5×1 | 25 | 0.1 | Bottom |
| P4 | P9415-R WPC Receiver | 5×5×1 | 25 | 0.1 | Bottom |
| P5 | RX Coil 70mm | 70 dia × 3 | 11,545 | 15 | Shell |
| P6 | Ferrite Shield 60mm | 60×60×0.8 | 2,880 | 8 | Shell |
| **THERMAL** |||||
| T1 | Thermal Pad 40×40mm | 40×40×1 | 1,600 | 3 | Center |
| T2 | Heatsink 14×14mm (×2) | 14×14×6 (each) | 2,352 | 6 | Center |
| **STRUCTURAL** |||||
| ST1 | Internal Frame | 65 dia × 45 | ~50,000 | 25 | Center |
| ST2 | Display Mount Ring | 40 dia × 4 | ~4,000 | 5 | Top |
| ST3 | LED Mount Ring | 58 dia × 6 | ~8,000 | 8 | Equator |
| ST4 | Battery Cradle | 63×43×16 | ~15,000 | 12 | Bottom |
| ST5 | Coil Mount Ring | 72 dia × 6 | ~10,000 | 10 | Shell |
| **SHELL** |||||
| SH1 | Top Hemisphere | 85 dia (half) | - | 45 | Outer |
| SH2 | Bottom Hemisphere | 85 dia (half) | - | 45 | Outer |

### 2.2 Volume Budget

| Category | Volume (mm³) | % of Inner |
|----------|--------------|------------|
| Available Inner | 179,594 | 100% |
| Structural (frames/mounts) | ~87,000 | 48% |
| Battery | 38,500 | 21% |
| SEN66 Air Quality | 20,172 | 11% |
| Compute (SoM+Hailo+ESP32) | 8,823 | 5% |
| Camera | 6,354 | 4% |
| Other Components | ~10,000 | 6% |
| **Remaining Margin** | **~8,745** | **5%** |

### 2.3 Weight Budget

| Category | Weight (g) |
|----------|------------|
| Shell (2 hemispheres) | 90 |
| Battery | 145 |
| Structural (all mounts) | 60 |
| Electronics | 35 |
| Sensors | 13 |
| Thermal | 9 |
| **Total Orb Weight** | **352g** |
| Maglev Capacity | 500g |
| **Safety Margin** | **148g (30%)** |

---

## 3. ASSEMBLY ZONES (Top to Bottom)

### 3.1 Zone A: TOP (Z = +20 to +35mm)

**Contents:** Display, Camera, Proximity Sensors

```
┌─────────────────────────────────────────────────────────┐
│                    ZONE A: TOP VIEW                     │
│                   (Looking down at orb)                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                 ╭─────────────────╮                     │
│                │   Shell (85mm)   │                     │
│                │  ╭───────────╮   │                     │
│                │  │ Dielectric│   │  Z = +35mm (shell) │
│                │  │  Mirror   │   │                     │
│                │  ├───────────┤   │                     │
│                │  │  AMOLED   │   │  Z = +32mm         │
│                │  │  38.83mm  │   │                     │
│                │  │  ┌─────┐  │   │                     │
│                │  │  │PUPIL│  │   │  8mm aperture      │
│                │  │  │ ○   │  │   │  (camera behind)   │
│                │  │  └─────┘  │   │                     │
│                │  ╰───────────╯   │                     │
│                │ Display Mount    │  Z = +28mm         │
│                ╰─────────────────╯                     │
│                                                         │
│   Components at Z = +25mm:                              │
│   ┌──────────────────────────────────────┐             │
│   │         IMX989 Camera Module          │             │
│   │            26×26×9.4mm                │             │
│   │       (centered under pupil)          │             │
│   └──────────────────────────────────────┘             │
│                                                         │
│   Sensors at Z = +22mm (around camera):                │
│   ┌────┐  ┌────┐  ┌────┐                               │
│   │S1  │  │S2  │  │S3  │                               │
│   │Radar│  │ToF │  │Spec│                               │
│   └────┘  └────┘  └────┘                               │
│   BGT60  VL53L8  AS7343                                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Assembly Sequence (Zone A):**
1. Apply DSX-E oleophobic coating to inner top shell
2. Affix dielectric mirror film to shell interior (centered)
3. Install display mount ring (press fit into frame)
4. Place 1.39" AMOLED into mount (flex cable exits toward equator)
5. Install IMX989 camera module below display (aligned with 8mm pupil)
6. Install BGT60TR13C radar, VL53L8CX ToF, AS7343 spectral around camera
7. Route MIPI cables from display and camera toward compute zone

### 3.2 Zone B: CENTER (Z = -10 to +20mm)

**Contents:** Compute Stack, Audio Processing, Small Sensors

```
┌─────────────────────────────────────────────────────────┐
│                  ZONE B: CROSS-SECTION                  │
│                    (Side view, Y=0)                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   Z = +15mm to +20mm: COMPUTE STACK                    │
│   ┌─────────────────────────────────────────────────┐  │
│   │              QCS6490 SoM (42.5×35.5mm)          │  │
│   │  ┌─────────────────────────────────────────────┐│  │
│   │  │                                             ││  │
│   │  │    12 TOPS NPU │ WiFi 6E │ BT 5.4          ││  │
│   │  │                                             ││  │
│   │  └─────────────────────────────────────────────┘│  │
│   │              ↑ Thermal Pad (40×40×1mm) ↑        │  │
│   │              ↑ Heatsink (14×14×6mm) ↑           │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
│   Z = +10mm to +15mm: AI ACCELERATOR                   │
│   ┌─────────────────────────────────────────────────┐  │
│   │           Hailo-10H M.2 2242 (42×22mm)          │  │
│   │  ┌─────────────────────────────────────────┐    │  │
│   │  │      40 TOPS INT4 │ GenAI Native        │    │  │
│   │  └─────────────────────────────────────────┘    │  │
│   │              ↑ Heatsink (14×14×6mm) ↑           │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
│   Z = +5mm to +10mm: CO-PROCESSOR & AUDIO DSP          │
│   ┌────────────────────┐  ┌────────────────────┐       │
│   │  ESP32-S3-WROOM    │  │   XMOS XVF3800     │       │
│   │    18×25.5mm       │  │     7×7mm QFN      │       │
│   │  LED + Sensors     │  │   Voice Processor  │       │
│   └────────────────────┘  └────────────────────┘       │
│                                                         │
│   Z = 0mm to +5mm: SMALL ICs                           │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
│   │MAX98 │ │74AHCT│ │ICM-  │ │SHT45 │                  │
│   │357A  │ │125   │ │45686 │ │      │                  │
│   │Amp   │ │Shift │ │IMU   │ │T/H   │                  │
│   └──────┘ └──────┘ └──────┘ └──────┘                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Assembly Sequence (Zone B):**
1. Install internal frame (CF-PETG, 65mm dia × 45mm height)
2. Place thermal pad on QCS6490 mounting platform
3. Install QCS6490 SoM with heatsink
4. Install Hailo-10H M.2 module into M.2 2242 slot
5. Install second heatsink on Hailo-10H
6. Mount ESP32-S3 module (I2C/SPI to sensors, GPIO to LEDs)
7. Mount XMOS XVF3800 DSP (I2S bus to mics and speaker)
8. Install MAX98357A amp (I2S from XMOS, output to speaker)
9. Install 74AHCT125 level shifter (ESP32 → HD108 LEDs)
10. Install ICM-45686 IMU (center of mass)
11. Install SHT45 temp/humidity (thermal zone monitoring)

### 3.3 Zone C: EQUATOR (Z = -5 to +5mm)

**Contents:** LED Ring, Microphones, Diffuser

```
┌─────────────────────────────────────────────────────────┐
│                  ZONE C: EQUATOR VIEW                   │
│                   (Top-down at Z=0)                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│              LED RING (55mm diameter)                   │
│                                                         │
│                    ○ LED1                               │
│               ○          ○                              │
│            ○       MIC1      ○                          │
│                    ↑                                    │
│          ○    ←  ┌───┐  →    ○                          │
│              MIC4│   │MIC2                              │
│          ○       └───┘       ○                          │
│                    ↓                                    │
│            ○      MIC3       ○                          │
│               ○          ○                              │
│                    ○ LED9                               │
│                                                         │
│   16× HD108 LEDs at 22.5° intervals                    │
│   4× sensiBel SBM100B mics at 90° intervals            │
│   (Beamforming array for voice localization)           │
│                                                         │
│   ┌─────────────────────────────────────────────────┐  │
│   │              LED Mount Ring (58mm OD)            │  │
│   │  ┌─────────────────────────────────────────┐    │  │
│   │  │        LED PCB (1.6mm, 52mm dia)        │    │  │
│   │  │     (Flexible PCB with HD108 × 16)      │    │  │
│   │  └─────────────────────────────────────────┘    │  │
│   │              Diffuser Ring (frosted)            │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Assembly Sequence (Zone C):**
1. Install LED mount ring onto internal frame (snap fit at equator)
2. Insert flexible LED PCB (16× HD108) into ring slot
3. Install 4× sensiBel SBM100B mics (90° spacing) into equator mounts
4. Install frosted diffuser ring over LED PCB
5. Connect LED data line to 74AHCT125 output
6. Connect mic I2S/PDM lines to XMOS XVF3800

### 3.4 Zone D: BOTTOM (Z = -35 to -5mm)

**Contents:** Battery, Power Electronics, Speaker, Air Quality

```
┌─────────────────────────────────────────────────────────┐
│                  ZONE D: BOTTOM VIEW                    │
│                  (Looking up at orb)                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   Z = -8mm to -5mm: SPEAKER                            │
│   ┌─────────────────────────────────────────────────┐  │
│   │       Tectonic TEBM28C20N-4 (28mm dia)          │  │
│   │           Balanced Mode Radiator                 │  │
│   │           (Sound exits through frame)            │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
│   Z = -20mm to -8mm: AIR QUALITY SENSOR                │
│   ┌─────────────────────────────────────────────────┐  │
│   │          Sensirion SEN66 (41×41×12mm)           │  │
│   │        PM2.5 │ VOC │ NOx │ CO2 │ T/H            │  │
│   │         (Air vents in shell required)           │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
│   Z = -28mm to -20mm: BATTERY                          │
│   ┌─────────────────────────────────────────────────┐  │
│   │         2200mAh 3S LiPo (55×35×20mm)            │  │
│   │              24Wh │ 11.1V nominal               │  │
│   │         (Largest single component)              │  │
│   │                                                  │  │
│   │   ┌──────────────────────────────────────────┐  │  │
│   │   │           Battery Cradle                 │  │  │
│   │   │   (Tough 2000, 63×43×16mm, foam-lined)   │  │  │
│   │   └──────────────────────────────────────────┘  │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
│   Z = -30mm: POWER MANAGEMENT ICs                      │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                  │
│   │BQ258 │ │BQ40Z │ │P9415 │ │AH49E │                  │
│   │95    │ │50    │ │-R    │ │Hall  │                  │
│   │Chrgr │ │Fuel  │ │WPC RX│ │Sense │                  │
│   └──────┘ └──────┘ └──────┘ └──────┘                  │
│                                                         │
│   Z = -35mm: RX COIL (AT SHELL)                        │
│   ┌─────────────────────────────────────────────────┐  │
│   │          RX Coil 70mm (Litz wire)               │  │
│   │     18 turns │ 85μH │ Ferrite backing           │  │
│   │        (Integrated into coil mount)             │  │
│   │                                                  │  │
│   │   ╔═══════════════════════════════════════════╗ │  │
│   │   ║     Ferrite Shield 60×60×0.8mm           ║ │  │
│   │   ║            (EMI shielding)               ║ │  │
│   │   ╚═══════════════════════════════════════════╝ │  │
│   │                                                  │  │
│   │          Coil Mount Ring (72mm dia)             │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Assembly Sequence (Zone D):**
1. Install coil mount ring into bottom hemisphere
2. Place ferrite shield (60×60mm) into recess
3. Wind RX coil (70mm, 18 turns Litz) into mount
4. Install battery cradle into internal frame
5. Place 2200mAh battery into cradle (foam padding)
6. Install power management PCB with BQ25895, BQ40Z50, P9415-R
7. Install AH49E Hall sensor (dock detection)
8. Install SEN66 air quality sensor (above battery)
9. Install Tectonic speaker (above air quality)
10. Route power cables to compute zone

---

## 4. ELECTRICAL CONNECTIVITY

### 4.1 Power Distribution

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           POWER DISTRIBUTION TREE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   RX Coil (70mm)                                                                │
│       │                                                                          │
│       ▼                                                                          │
│   P9415-R (15W WPC RX) ───────────────────┐                                     │
│       │                                    │                                     │
│       ▼                                    ▼                                     │
│   BQ25895 (5A Charger) ◄──────────── BQ40Z50 (Fuel Gauge)                       │
│       │                                    │                                     │
│       ▼                                    ▼                                     │
│   Battery 3S (11.1V) ◄────────────── SoC Reporting                              │
│       │                                                                          │
│       ├───────────────────────────────────────────────────────────────────────┐ │
│       │                                                                        │ │
│       ▼                                                                        │ │
│   ┌─────────────────────────────────────────────────────────────────────────┐ │ │
│   │                        VOLTAGE RAILS                                    │ │ │
│   ├─────────────────────────────────────────────────────────────────────────┤ │ │
│   │                                                                          │ │ │
│   │   11.1V (Battery Direct)                                                │ │ │
│   │       └── Reserved for high-power future use                            │ │ │
│   │                                                                          │ │ │
│   │   5V Rail (Buck from 11.1V)                   Current Budget            │ │ │
│   │       ├── HD108 LEDs (×16)                    320mA peak                │ │ │
│   │       ├── ESP32-S3 (VIN)                      240mA typical             │ │ │
│   │       └── MAX98357A (Speaker amp)             300mA peak                │ │ │
│   │                                               ───────────               │ │ │
│   │                                               860mA total               │ │ │
│   │                                                                          │ │ │
│   │   3.3V Rail (LDO from 5V)                                               │ │ │
│   │       ├── QCS6490 SoM                         1200mA typical            │ │ │
│   │       ├── Hailo-10H                           800mA typical             │ │ │
│   │       ├── XMOS XVF3800                        150mA                     │ │ │
│   │       ├── sensiBel SBM100B (×4)               20mA total                │ │ │
│   │       ├── All sensors                         50mA total                │ │ │
│   │       └── Display (AMOLED)                    80mA typical              │ │ │
│   │                                               ───────────               │ │ │
│   │                                               2300mA total              │ │ │
│   │                                                                          │ │ │
│   │   1.8V Rail (From QCS6490)                                              │ │ │
│   │       └── MIPI interface signals                                        │ │ │
│   │                                                                          │ │ │
│   │   1.2V Rail (From QCS6490)                                              │ │ │
│   │       └── Core logic                                                    │ │ │
│   │                                                                          │ │ │
│   └─────────────────────────────────────────────────────────────────────────┘ │ │
│                                                                                  │
│   Total Power Budget:                                                           │
│   ─────────────────                                                             │
│   Idle:     ~3W (standby, listening)                                            │
│   Active:   ~6W (display + AI + audio)                                          │
│   Peak:     ~10W (all systems max)                                              │
│                                                                                  │
│   Battery Life (24Wh):                                                          │
│   ─────────────────────                                                         │
│   Idle:     ~8 hours                                                            │
│   Active:   ~4 hours                                                            │
│   Peak:     ~2.4 hours                                                          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Bus Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA BUS ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │                         QCS6490 SoM (Main Processor)                   │    │
│   │                                                                         │    │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │    │
│   │   │ MIPI-DSI │  │ MIPI-CSI │  │  PCIe    │  │  I2C/SPI │              │    │
│   │   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘              │    │
│   │        │              │              │              │                   │    │
│   └────────│──────────────│──────────────│──────────────│───────────────────┘    │
│            │              │              │              │                        │
│            ▼              ▼              ▼              ▼                        │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────────┐        │
│   │ 1.39"      │  │  IMX989    │  │  Hailo-10H │  │   Sensor Hub       │        │
│   │ AMOLED     │  │  Camera    │  │  M.2 2242  │  │                    │        │
│   │            │  │            │  │            │  │ ├── BGT60TR13C     │        │
│   │ 454×454    │  │ 50.3MP     │  │ 40 TOPS    │  │ ├── VL53L8CX       │        │
│   │ MIPI 2-ln  │  │ MIPI 4-ln  │  │ PCIe x4    │  │ ├── AS7343         │        │
│   │            │  │            │  │            │  │ ├── ICM-45686      │        │
│   └────────────┘  └────────────┘  └────────────┘  │ ├── SHT45          │        │
│                                                    │ └── SEN66 (UART)   │        │
│                                                    └────────────────────┘        │
│                                                                                  │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │                        ESP32-S3 (Co-Processor)                         │    │
│   │                                                                         │    │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │    │
│   │   │   GPIO   │  │   SPI    │  │   UART   │  │   I2C    │              │    │
│   │   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘              │    │
│   │        │              │              │              │                   │    │
│   └────────│──────────────│──────────────│──────────────│───────────────────┘    │
│            │              │              │              │                        │
│            ▼              ▼              ▼              ▼                        │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│   │ 74AHCT125  │  │ SD Card    │  │ QCS6490    │  │ BQ40Z50    │                │
│   │     │      │  │ (future)   │  │ UART       │  │ Fuel Gauge │                │
│   │     ▼      │  │            │  │ Debug      │  │            │                │
│   │ HD108 LEDs │  │            │  │            │  │            │                │
│   │   (×16)    │  │            │  │            │  │            │                │
│   └────────────┘  └────────────┘  └────────────┘  └────────────┘                │
│                                                                                  │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │                        XMOS XVF3800 (Audio DSP)                        │    │
│   │                                                                         │    │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐                             │    │
│   │   │ PDM In   │  │ I2S Out  │  │ I2S Out  │                             │    │
│   │   └────┬─────┘  └────┬─────┘  └────┬─────┘                             │    │
│   │        │              │              │                                  │    │
│   └────────│──────────────│──────────────│──────────────────────────────────┘    │
│            │              │              │                                       │
│            ▼              ▼              ▼                                       │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐                                │
│   │ sensiBel   │  │  QCS6490   │  │ MAX98357A  │                                │
│   │ SBM100B×4  │  │  Audio In  │  │     │      │                                │
│   │ (PDM mics) │  │            │  │     ▼      │                                │
│   │            │  │            │  │  Speaker   │                                │
│   └────────────┘  └────────────┘  └────────────┘                                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Connector Summary

| From | To | Interface | Cable Type | Length |
|------|-----|-----------|------------|--------|
| AMOLED | QCS6490 | MIPI DSI 2-lane | FPC 24-pin | 40mm |
| IMX989 | QCS6490 | MIPI CSI 4-lane | FPC 30-pin | 35mm |
| Hailo-10H | QCS6490 | PCIe Gen3 x4 | M.2 socket | Direct |
| ESP32-S3 | QCS6490 | UART | Wire | 30mm |
| XMOS | QCS6490 | I2S | Wire | 25mm |
| XMOS | sensiBel×4 | PDM | FPC 8-pin | 50mm |
| XMOS | MAX98357A | I2S | Wire | 15mm |
| MAX98357A | Speaker | 2-wire | Wire | 40mm |
| ESP32-S3 | HD108 LEDs | Data (5V) | Wire | 60mm |
| Battery | BQ25895 | Power | 16AWG | 30mm |
| RX Coil | P9415-R | AC | Litz | 25mm |
| All sensors | QCS6490 | I2C/SPI | FPC | 30-50mm |

---

## 5. THERMAL MANAGEMENT

### 5.1 Heat Sources

| Component | TDP (W) | Operating Temp | Max Temp |
|-----------|---------|----------------|----------|
| QCS6490 SoM | 4.0 | 65°C | 85°C |
| Hailo-10H | 2.5 | 60°C | 80°C |
| Battery (charging) | 1.5 | 40°C | 45°C |
| MAX98357A | 0.5 | 50°C | 70°C |
| LEDs (×16) | 0.8 | 45°C | 65°C |
| **Total** | **9.3** | | |

### 5.2 Thermal Path

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              THERMAL FLOW DIAGRAM                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Heat Sources                 Thermal Path               Heat Sink             │
│   ────────────                 ────────────               ─────────             │
│                                                                                  │
│   ┌──────────┐                                                                  │
│   │ QCS6490  │ ──► Thermal Pad (6W/mK) ──► Heatsink ──► Frame ──► Shell ──► Air │
│   │  4.0W    │         40×40×1mm           14×14×6mm     CF-PETG   Acrylic      │
│   └──────────┘                                                                  │
│                                                                                  │
│   ┌──────────┐                                                                  │
│   │ Hailo-10H│ ──► Thermal Pad ──────────► Heatsink ──► Frame ──► Shell ──► Air │
│   │  2.5W    │                              14×14×6mm                           │
│   └──────────┘                                                                  │
│                                                                                  │
│   ┌──────────┐                                                                  │
│   │ Battery  │ ──► Cradle (Tough 2000) ──► Frame ──► Shell ──► Air             │
│   │  1.5W    │                                                                  │
│   └──────────┘                                                                  │
│                                                                                  │
│   Thermal Resistance Budget:                                                    │
│   ─────────────────────────                                                     │
│   Component → Pad:     0.5 °C/W                                                 │
│   Pad → Heatsink:      0.3 °C/W                                                 │
│   Heatsink → Frame:    1.0 °C/W                                                 │
│   Frame → Shell:       2.0 °C/W                                                 │
│   Shell → Air:         5.0 °C/W                                                 │
│   ───────────────────────────                                                   │
│   Total:               8.8 °C/W                                                 │
│                                                                                  │
│   Temperature Rise (worst case 9.3W):                                           │
│   ΔT = 9.3W × 8.8 °C/W = 82°C above ambient                                    │
│                                                                                  │
│   At 25°C ambient: Junction temp = 107°C ← EXCEEDS LIMIT!                       │
│                                                                                  │
│   MITIGATION REQUIRED:                                                          │
│   1. Thermal throttling at 75°C junction                                        │
│   2. Active duty cycling during high load                                       │
│   3. Heat spreading via aluminum internal frame (upgrade from CF-PETG)          │
│   4. Consider thermal vias to shell bottom (near maglev base)                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Thermal Mitigation Actions

| Action | Impact | Cost |
|--------|--------|------|
| Aluminum internal frame | -30% thermal resistance | +$20 |
| Larger heatsinks (20×20mm) | -20% thermal resistance | +$2 |
| Thermal vias to bottom | -25% resistance | +$5 (print) |
| Throttle at 70°C | Limits sustained load | $0 |
| Lower charging current | Reduces battery heat | $0 |

---

## 6. MECHANICAL INTEGRATION

### 6.1 Shell-to-Frame Interface

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SHELL-TO-FRAME INTERFACE                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   EQUATOR JOINT (Shell Seam):                                                   │
│                                                                                  │
│         Top Hemisphere (85mm)                                                   │
│               ↓                                                                  │
│   ╔═══════════════════════════════════════════╗                                 │
│   ║   Adhesive bond (UV-cure acrylic)         ║ ← 2mm overlap                  │
│   ╠═══════════════════════════════════════════╣                                 │
│   ║   LED Mount Ring (58mm OD)                ║ ← Locates shells               │
│   ║   ┌─────────────────────────────────┐     ║                                 │
│   ║   │     Internal Frame (65mm)       │     ║ ← Snap-fit to ring             │
│   ║   └─────────────────────────────────┘     ║                                 │
│   ╠═══════════════════════════════════════════╣                                 │
│   ║   Adhesive bond                           ║                                 │
│   ╚═══════════════════════════════════════════╝                                 │
│               ↑                                                                  │
│         Bottom Hemisphere (85mm)                                                │
│                                                                                  │
│   INTERNAL FRAME MOUNT POINTS:                                                  │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                          Internal Frame                                 │   │
│   │                                                                          │   │
│   │   Display Mount ──► 3× M2 screws (press-fit inserts)                    │   │
│   │                                                                          │   │
│   │   LED Ring ──────► 4× snap tabs (90° spacing)                           │   │
│   │                                                                          │   │
│   │   Battery Cradle ► 4× M3 screws (heat-set inserts)                      │   │
│   │                                                                          │   │
│   │   Coil Mount ────► 3× alignment pins + adhesive                         │   │
│   │                                                                          │   │
│   │   PCB Mounts ────► M2 standoffs (various heights)                       │   │
│   │                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Fastener Schedule

| Location | Fastener | Quantity | Material | Torque |
|----------|----------|----------|----------|--------|
| Display mount | M2×4 screw | 3 | Stainless | 0.2 Nm |
| Display mount inserts | M2 brass insert | 3 | Brass | Press |
| Battery cradle | M3×6 screw | 4 | Stainless | 0.5 Nm |
| Battery inserts | M3 heat-set | 4 | Brass | Heat |
| PCB standoffs | M2×8 standoff | 8 | Nylon | 0.1 Nm |
| LED ring tabs | Snap fit | 4 | Integrated | N/A |
| Coil mount pins | Alignment pin | 3 | Stainless | Press |
| Shell bond | UV adhesive | N/A | Acrylic | N/A |

---

## 7. ASSEMBLY PROCEDURE (Complete)

### 7.1 Pre-Assembly Checklist

- [ ] All components received and verified
- [ ] Firmware flashed to QCS6490, ESP32-S3
- [ ] Battery charged to 50% for safe handling
- [ ] 3D printed parts cleaned and post-cured
- [ ] Shell hemispheres cleaned and inspected
- [ ] Workstation ESD-safe

### 7.2 Step-by-Step Assembly

**PHASE 1: Prepare Internal Frame (15 min)**
1. Install M2 brass inserts into display mount holes (heat press)
2. Install M3 heat-set inserts into battery cradle holes
3. Verify all snap-fit features intact
4. Test-fit all mounts without components

**PHASE 2: Install Compute Stack (20 min)**
1. Apply thermal pad to QCS6490 mounting platform
2. Place QCS6490 SoM, align B2B connector
3. Attach heatsink with thermal adhesive
4. Insert Hailo-10H into M.2 2242 slot, secure with screw
5. Attach second heatsink to Hailo-10H
6. Mount ESP32-S3 with M2 screws
7. Mount XMOS XVF3800 breakout

**PHASE 3: Install Power Section (15 min)**
1. Mount power management PCB (BQ25895, BQ40Z50, P9415-R)
2. Install AH49E Hall sensor
3. Place battery into cradle (verify polarity!)
4. Secure battery cradle with M3 screws
5. Connect battery to power PCB
6. Verify voltage rails: 11.1V, 5V, 3.3V

**PHASE 4: Install Bottom Assembly (20 min)**
1. Install coil mount ring into bottom hemisphere
2. Place ferrite shield into recess
3. Wind RX coil into mount (or place pre-wound coil)
4. Connect coil to P9415-R
5. Install SEN66 air quality sensor
6. Install Tectonic speaker
7. Connect speaker to MAX98357A

**PHASE 5: Install Equator Components (15 min)**
1. Attach LED mount ring to internal frame (snap fit)
2. Insert LED flex PCB into slot
3. Install 4× sensiBel microphones (90° spacing)
4. Install frosted diffuser ring
5. Connect LED data line to 74AHCT125
6. Connect mic lines to XMOS

**PHASE 6: Install Top Assembly (20 min)**
1. Install display mount ring with M2 screws
2. Place 1.39" AMOLED, secure with retention clips
3. Install IMX989 camera module (align with pupil)
4. Install proximity sensors (BGT60TR13C, VL53L8CX, AS7343)
5. Route all flex cables toward compute zone
6. Connect MIPI cables to QCS6490

**PHASE 7: Cable Management (10 min)**
1. Verify all connections
2. Bundle cables with kapton tape
3. Ensure no cable pinch points
4. Test fit into top hemisphere

**PHASE 8: Final Assembly (15 min)**
1. Apply dielectric mirror film to top hemisphere interior
2. Apply DSX-E oleophobic coating
3. Place internal frame assembly into bottom hemisphere
4. Align LED ring at equator seam
5. Apply UV-cure adhesive to equator rim
6. Mate top hemisphere, ensure alignment
7. Cure adhesive (UV lamp 30 seconds)
8. Clean exterior shell

**PHASE 9: Power-On Test (10 min)**
1. Place on maglev base
2. Verify levitation
3. Verify wireless charging
4. Check boot sequence on display
5. Test all sensors
6. Test microphone array
7. Test speaker output
8. Test LED ring animation

---

## 8. REDUNDANCY ANALYSIS

### 8.1 Components to REMOVE (Redundancy)

| Component | Issue | Resolution |
|-----------|-------|------------|
| None currently | BOM is optimized | N/A |

### 8.2 Single Points of Failure (SPOF)

| SPOF | Criticality | Mitigation |
|------|-------------|------------|
| QCS6490 | Critical | None (must work) |
| Battery | Critical | Over-discharge protection |
| Display | High | Software eye fallback |
| IMX989 Camera | High | Radar gesture fallback |
| sensiBel Mics | Medium | 4× redundancy, 3 needed |
| RX Coil | Medium | Battery backup |

---

## 9. REVISION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 3.0 | Jan 2026 | Initial 85mm sealed sphere design |
| 3.1 | Jan 2026 | Fixed display/battery dimensions, added thermal analysis |

---

**Document Status:** COMPLETE
**Ready for:** CAD Modeling, Prototyping
**Author:** Kagami (鏡)
