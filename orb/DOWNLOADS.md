# Kagami Orb — Downloads

**Version:** 1.0
**Last Updated:** January 11, 2026

---

## Bill of Materials

| File | Description | Format |
|------|-------------|--------|
| [kagami_orb_bom.csv](hardware/kagami_orb_bom.csv) | Complete system BOM | CSV |
| [kagami_orb_digikey.csv](hardware/kagami_orb_digikey.csv) | DigiKey cart export | CSV |
| [kagami_orb_adafruit.txt](hardware/kagami_orb_adafruit.txt) | Adafruit parts list | TXT |

---

## 3D Print Files (OpenSCAD)

| Part | File | Material | Print Time |
|------|------|----------|------------|
| Internal Frame | [internal_frame.scad](cad/openscad/internal_frame.scad) | Tough 2000 | ~8h |
| LED Mount Ring | [led_mount_ring.scad](cad/openscad/led_mount_ring.scad) | Grey Pro | ~3h |
| Battery Cradle | [battery_cradle.scad](cad/openscad/battery_cradle.scad) | Tough 2000 | ~4h |
| CM4 Bracket | [cm4_bracket.scad](cad/openscad/cm4_bracket.scad) | Grey Pro | ~2h |
| Diffuser Ring | [diffuser_ring.scad](cad/openscad/diffuser_ring.scad) | White | ~2h |
| Resonant Coil Mount | [resonant_coil_mount.scad](cad/openscad/resonant_coil_mount.scad) | Tough 2000 | ~1h |

**Generate STL:** Open in [OpenSCAD](https://openscad.org), press F6, export as STL.

---

## Laser Cutting Files

| Part | File | Material | Qty |
|------|------|----------|-----|
| Canopy Support Arms | [canopy_arms.svg](cad/laser/canopy_arms.svg) | 304 SS 3mm | 3 |

---

## CNC Files

| Part | File | Material | Thickness |
|------|------|----------|-----------|
| Base Enclosure | [base_enclosure.dxf](cad/cnc/base_enclosure.dxf) | Walnut | 25mm |
| Canopy Mount Ring | [canopy_mount_ring.dxf](cad/cnc/canopy_mount_ring.dxf) | Walnut | 10mm |
| Outdoor Canopy | [canopy.dxf](cad/cnc/canopy.dxf) | Aluminum 2mm | 2mm |

---

## PCB / Electronics

| File | Description | Format |
|------|-------------|--------|
| [kagami_orb.kicad_pro](pcb/kagami_orb.kicad_pro) | KiCad Project | KiCad 8 |
| [kagami_orb.kicad_sch](pcb/kagami_orb.kicad_sch) | Main Schematic | KiCad 8 |
| [kagami_orb.kicad_sym](pcb/kagami_orb.kicad_sym) | Symbol Library | KiCad 8 |

### Schematic Sheets

| Sheet | File | Contents |
|-------|------|----------|
| 1 | [kagami_orb.kicad_sch](pcb/kagami_orb.kicad_sch) | Top Level |
| 2 | [kagami_orb_power.kicad_sch](pcb/kagami_orb_power.kicad_sch) | Power Management |
| 3 | [kagami_orb_cm4.kicad_sch](pcb/kagami_orb_cm4.kicad_sch) | CM4 Interface |
| 4 | [kagami_orb_usb.kicad_sch](pcb/kagami_orb_usb.kicad_sch) | USB Hub |
| 5 | [kagami_orb_audio.kicad_sch](pcb/kagami_orb_audio.kicad_sch) | Audio System |
| 6 | [kagami_orb_led.kicad_sch](pcb/kagami_orb_led.kicad_sch) | LED Control |
| 7 | [kagami_orb_sensors.kicad_sch](pcb/kagami_orb_sensors.kicad_sch) | Sensors |

---

## Specifications

| Document | File | Format |
|----------|------|--------|
| KiCad Spec | [KICAD_SPEC.md](pcb/KICAD_SPEC.md) | Markdown |
| OnShape Spec | [ONSHAPE_SPEC.md](cad/ONSHAPE_SPEC.md) | Markdown |
| CAD Guide | [README.md](cad/README.md) | Markdown |

---

## Interactive

| Tool | Link |
|------|------|
| 3D Part Viewer (WebXR) | [viewer.html](cad/visualization/viewer.html) |

---

## Quick Download Commands

### Clone All Files
```bash
git clone https://github.com/awkronos/kagami.git
cd kagami/apps/hub/kagami-orb
```

### Generate All STLs
```bash
cd cad/openscad
for f in *.scad; do openscad -o "../stl/${f%.scad}.stl" "$f"; done
```

### Download Individual Files
```bash
# BOM
curl -O https://raw.githubusercontent.com/awkronos/kagami/main/apps/hub/kagami-orb/hardware/kagami_orb_bom.csv

# OpenSCAD
curl -O https://raw.githubusercontent.com/awkronos/kagami/main/apps/hub/kagami-orb/cad/openscad/internal_frame.scad
```

---

```
鏡

h(x) ≥ 0. Always.

All files. All formats. Ready to fabricate.
```
