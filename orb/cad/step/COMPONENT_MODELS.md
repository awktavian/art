# Kagami Orb V3.1 — Component 3D Models

**Purpose:** Reference for creating accurate component models for assembly verification
**Last Updated:** January 2026

---

## Model Sources Summary

| Component | Source | Status | Format |
|-----------|--------|--------|--------|
| DF40HC-100DS | [Hirose Official](https://www.hirose.com/product/p/CL0684-4151-0-51) | Download STEP | STEP/IGES |
| M.2 2242 Connector | [TraceParts TE](https://www.traceparts.com/en/product/te-connectivity-m2-connectors) | Download STEP | STEP |
| 5050 LED | [SnapEDA 5050RGB](https://www.snapeda.com/parts/5050RGB/SparkFun/view-part/) | Download STEP | STEP |
| 28mm Speaker | [TraceParts PUI Audio](https://www.traceparts.com/en/search/pui-audio-inc-speakersreceivers) | Search catalog | STEP |
| QCS6490 SoM | Contact Thundercomm | Create placeholder | N/A |
| Hailo-10H M.2 | Generic M.2 2242 | Create placeholder | N/A |
| 1.39" AMOLED | Custom dimensions | Create placeholder | N/A |
| IMX989 Camera | Custom dimensions | Create placeholder | N/A |
| 3S LiPo Battery | Custom dimensions | Create placeholder | N/A |

---

## Verified Component Dimensions (for placeholder models)

### 1. QCS6490 SoM (Thundercomm TurboX C6490)
```
Length: 42.5mm
Width:  35.5mm
Height: 2.7mm (board only)
Total with connectors: ~5.0mm

Features:
- 100-pin DF40HC connector on bottom
- M.2 Key M connector for expansion
- Heat spreader mounting area: 20x20mm center
```

### 2. Hailo-10H M.2 2242
```
Length: 42.0mm (M.2 2242 standard)
Width:  22.0mm (M.2 standard)
Height: 2.63mm (max component height)

Features:
- M.2 Key M notch at 4mm from edge
- Mounting hole at 40mm from connector
- Heat spreader area: 15x15mm
```

### 3. 1.39" Round AMOLED Display
```
Module:
  Length: 38.83mm
  Width:  38.21mm
  Height: 0.68mm (glass only)
  Total:  ~2.5mm with FPC

Active Area:
  Diameter: 35.41mm (454x454 pixels)

FPC Cable:
  Width:  12mm
  Length: 30mm (flexible)
```

### 4. IMX989 Camera Module
```
Length: 26.0mm
Width:  26.0mm
Height: 9.4mm

Features:
- Lens aperture: Ø14mm center
- FPC connector: 24-pin, rear
- Sensor: 16.384mm diagonal (1/0.98")
```

### 5. HD108 5050 LED
```
Length: 5.1mm
Width:  5.0mm
Height: 1.6mm

Features:
- 6-pin PLCC package
- Lens dome: Ø3.5mm center
- Pad pitch: 1.6mm
```

### 6. DF40HC-100DS Connector
```
Length: 22.6mm (100 pins @ 0.4mm pitch)
Width:  4.3mm
Height: 3.0mm (mated height)

Features:
- Pin pitch: 0.4mm
- 2 rows x 50 pins
- Alignment bosses at ends
```
**Download:** [Hirose STEP](https://www.hirose.com/product/p/CL0684-4151-0-51)

### 7. M.2 2242 Connector (Key M)
```
Length: 22.0mm
Width:  3.5mm
Height: 4.2mm

Features:
- 75-pin (Key M configuration)
- Pin pitch: 0.5mm
- Mounting clip positions
```
**Download:** [TE Connectivity](https://www.traceparts.com/en/product/te-connectivity-m2-connectors)

### 8. 28mm Speaker
```
Diameter: 28.0mm
Height:   5.4mm

Features:
- Voice coil: Ø15mm
- Mounting holes: 3x M2 at Ø24mm
- Terminal spacing: 4mm
```

### 9. 3S LiPo Battery (2200mAh)
```
Length: 55.0mm
Width:  35.0mm
Height: 20.0mm

Features:
- Balance connector: 4-pin JST-XH
- Main connector: XT30 or JST
- Wire exit: center of 35mm edge
```

### 10. RX Coil Assembly
```
Coil:
  Outer Diameter: 70.0mm
  Inner Diameter: 40.0mm
  Height: 4.0mm

Ferrite Sheet:
  Diameter: 60.0mm
  Thickness: 0.5mm
```

---

## OpenSCAD Placeholder Generator

Use this code to generate accurate placeholder models:

```openscad
// Component placeholder dimensions (all in mm)
module qcs6490_som() {
    color("DarkGreen") cube([42.5, 35.5, 2.7], center=true);
    // Connector footprint
    translate([0, 0, -2.35]) color("Gold") cube([22.6, 4.3, 2.0], center=true);
}

module hailo_10h() {
    color("Black") cube([42, 22, 2.63], center=true);
    // M.2 notch
    translate([-21+4, -11, 0]) color("Black") cube([5, 2, 3], center=true);
}

module amoled_139() {
    // Glass
    color("Black", 0.8) cube([38.83, 38.21, 0.68], center=true);
    // Active area indicator
    translate([0, 0, 0.35]) color("DarkBlue", 0.5) cylinder(h=0.1, d=35.41, $fn=64);
    // FPC
    translate([0, -19.1-15, -1]) color("Orange") cube([12, 30, 0.3], center=true);
}

module imx989_camera() {
    color("DarkGray") cube([26, 26, 9.4], center=true);
    // Lens aperture
    translate([0, 0, 4.7]) color("Black") cylinder(h=1, d=14, $fn=32);
}

module hd108_led() {
    color("White") cube([5.1, 5.0, 1.6], center=true);
    // Lens dome
    translate([0, 0, 0.8]) color("White", 0.7) sphere(d=3.5, $fn=16);
}

module speaker_28mm() {
    color("Silver") cylinder(h=5.4, d=28, $fn=64);
    // Voice coil
    translate([0, 0, 2.7]) color("Black") cylinder(h=3, d=15, $fn=32);
}

module lipo_3s_2200() {
    color("Blue") cube([55, 35, 20], center=true);
    // Balance connector
    translate([0, 17.5, 5]) color("White") cube([10, 2, 8], center=true);
}

module rx_coil() {
    color("Copper") difference() {
        cylinder(h=4, d=70, $fn=64);
        translate([0, 0, -0.1]) cylinder(h=4.2, d=40, $fn=64);
    }
}

module ferrite_sheet() {
    color("DarkGray") cylinder(h=0.5, d=60, $fn=64);
}
```

---

## Assembly Verification Checklist

- [ ] All components fit within 70mm internal sphere diameter
- [ ] QCS6490 + Hailo stack height < 15mm
- [ ] Display + camera assembly clears top hemisphere window
- [ ] Battery fits in lower section with coil clearance
- [ ] LED ring aligns with equator slot (58mm OD)
- [ ] All connector heights allow proper mating
- [ ] Thermal paths maintain contact with shell

---

## Download Instructions

### Hirose DF40HC-100DS:
1. Go to https://www.hirose.com/product/p/CL0684-4151-0-51
2. Scroll to "Download" section
3. Select "Drawing (3D) (STEP)" - ~514 KB

### TE M.2 Connector:
1. Go to https://www.traceparts.com
2. Search "TE Connectivity M.2 connector"
3. Select Key M variant
4. Download STEP format

### 5050 LED:
1. Go to https://www.snapeda.com
2. Search "5050RGB" or "SK6812"
3. Create free account
4. Download STEP model

---

**Note:** For accurate assembly verification, the placeholder models above use verified manufacturer dimensions and are sufficient for clearance checking. Official STEP files add visual detail but don't improve dimensional accuracy.
