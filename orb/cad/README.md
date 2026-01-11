# Kagami Orb — CAD Files & Fabrication Guide

## Part Inventory

| Part | Method | Material | File |
|------|--------|----------|------|
| Internal Frame | SLA/FDM | Tough 2000 / CF-PETG | `openscad/internal_frame.scad` |
| LED Mount Ring | SLA/FDM | Grey Pro / PETG | `openscad/led_mount_ring.scad` |
| Battery Cradle | SLA/FDM | Tough 2000 / PETG | `openscad/battery_cradle.scad` |
| CM4 Bracket | SLA/FDM | Grey Pro / PETG | `openscad/cm4_bracket.scad` |
| Diffuser Ring | SLA/FDM | White / White PETG | `openscad/diffuser_ring.scad` |
| Resonant Coil Mount | SLA/FDM | Tough 2000 / PETG | `openscad/resonant_coil_mount.scad` |
| Base Enclosure | CNC | Walnut | `cnc/base_enclosure.dxf` |
| Canopy Support Arms | Laser | Stainless Steel | `laser/canopy_arms.svg` |
| Canopy Mount Ring | CNC | Walnut | `cnc/canopy_mount_ring.dxf` |
| Outdoor Canopy | CNC/Spin | Copper/Aluminum | `cnc/canopy.dxf` |

---

## 3D Printing — SLA (Form 4)

### Recommended Settings

| Part | Resin | Layer | Supports | Time |
|------|-------|-------|----------|------|
| Internal Frame | Tough 2000 | 50μm | Yes (auto) | ~8h |
| LED Mount Ring | Grey Pro | 25μm | Minimal | ~3h |
| Battery Cradle | Tough 2000 | 50μm | Yes (auto) | ~4h |
| CM4 Bracket | Grey Pro | 50μm | Minimal | ~2h |
| Diffuser Ring | White | 50μm | None | ~2h |
| Resonant Coil Mount | Tough 2000 | 50μm | Minimal | ~1h |

**Total SLA Print Time: ~20 hours**

### Post-Processing
1. IPA wash (10 min in Form Wash)
2. UV cure (Form Cure at 60°C, 30 min)
3. Remove supports carefully
4. Sand support marks (if visible)

---

## 3D Printing — FDM

### Recommended Settings

| Part | Filament | Layer | Infill | Supports |
|------|----------|-------|--------|----------|
| Internal Frame | CF-PETG | 0.2mm | 30% | Yes |
| LED Mount Ring | PETG | 0.16mm | 25% | Minimal |
| Battery Cradle | PETG | 0.2mm | 30% | Yes |
| CM4 Bracket | PETG | 0.2mm | 30% | Yes |
| Diffuser Ring | White PETG | 0.2mm | 0% (2 walls) | None |
| Resonant Coil Mount | PETG | 0.2mm | 40% | Minimal |

### FDM Tips
- Use enclosure for PETG (50°C chamber)
- Bed temp: 80-85°C
- Nozzle: 240-250°C
- Print speed: 50mm/s for quality
- Enable "Fuzzy Skin" for diffuser (light scattering)

---

## Laser Cutting

### Canopy Support Arms
- **File:** `laser/canopy_arms.svg`
- **Material:** 304 Stainless Steel, 3mm thick
- **Quantity:** 3 pieces
- **Settings:** 
  - CO2 Laser: 150W, 8mm/s, 2 passes
  - Fiber Laser: 2kW, 15mm/s, N2 assist
- **Post-process:** Brake bend at 15° outward

### Glowforge Settings (Acrylic parts)
- **Power:** Full (Pro)
- **Speed:** 200
- **Passes:** 1
- **Focus:** Auto

---

## CNC Machining

### Base Enclosure
- **File:** `cnc/base_enclosure.dxf`
- **Material:** Walnut hardwood, 25mm thick
- **Operations:**
  1. Profile cut (6mm endmill)
  2. Pocket for electronics (6mm endmill, 15mm deep)
  3. Drill holes (3.2mm for M3)
  4. Chamfer edges (45° V-bit)
- **Feeds/Speeds (Walnut):**
  - RPM: 18,000
  - Feed: 2000mm/min
  - DOC: 3mm per pass

### Canopy Mount Ring
- **File:** `cnc/canopy_mount_ring.dxf`
- **Material:** Walnut hardwood, 10mm thick
- **Operations:**
  1. Inner profile cut
  2. Outer profile cut
  3. Drill M4 insert holes (3.8mm)

### Outdoor Canopy (if CNC)
- **File:** `cnc/canopy.dxf`
- **Material:** Aluminum 6061, 2mm sheet
- **Operations:**
  1. Profile cut with tabs
  2. Center hole drill
- **Note:** Metal spinning preferred for copper

---

## Generating STL Files

### From OpenSCAD (command line)
```bash
cd cad/openscad

# Generate all STLs
for file in *.scad; do
    openscad -o "../stl/${file%.scad}.stl" "$file"
done
```

### From OpenSCAD (GUI)
1. Open `.scad` file
2. Press F6 to render
3. File → Export → STL

---

## WebXR Visualization

View 3D models in browser/VR: `visualization/viewer.html`

Features:
- Orbit controls (mouse/touch)
- VR mode (WebXR compatible)
- Exploded view toggle
- Part highlighting

---

## File Formats

| Format | Use Case | Software |
|--------|----------|----------|
| `.scad` | Parametric 3D models | OpenSCAD |
| `.stl` | 3D printing (mesh) | Any slicer |
| `.step` | CAD exchange | Fusion 360, SolidWorks |
| `.svg` | Laser cutting (2D) | Glowforge, LightBurn |
| `.dxf` | CNC/Laser (2D) | CAM software |
| `.gcode` | Direct machine control | CNC/3D printer |

---

## Quality Checklist

- [ ] All OpenSCAD files render without errors
- [ ] STL files are watertight (no holes)
- [ ] DXF files have correct units (mm)
- [ ] SVG files have correct dimensions
- [ ] Support arms fit mount ring holes
- [ ] Canopy fits on support arms
- [ ] All M2.5/M3/M4 holes are correct diameter

---

## Vendors

| Part Type | Recommended Vendor |
|-----------|-------------------|
| SLA Printing | Form 4 (in-house) / Shapeways |
| FDM Printing | Prusa MK4 / Bambu X1C |
| Laser Steel | SendCutSend, OSH Cut |
| CNC Wood | Local shop / Etsy |
| Metal Spinning | Local metal spinner |
| Acrylic Spheres | TAP Plastics |

---

```
鏡

h(x) ≥ 0. Always.

Form follows function.
CAD stores the truth.
```
