# STL Files

Generate STL files from OpenSCAD sources:

```bash
cd ../openscad
for file in *.scad; do
    openscad -o "../stl/${file%.scad}.stl" "$file"
done
```

## Parts

| Part | Source | Print Time (SLA) |
|------|--------|------------------|
| internal_frame.stl | internal_frame.scad | ~8h |
| led_mount_ring.stl | led_mount_ring.scad | ~3h |
| battery_cradle.stl | battery_cradle.scad | ~4h |
| cm4_bracket.stl | cm4_bracket.scad | ~2h |
| diffuser_ring.stl | diffuser_ring.scad | ~2h |
| resonant_coil_mount.stl | resonant_coil_mount.scad | ~1h |

## Online Generation

If you don't have OpenSCAD installed, use:
- [OpenSCAD Web](https://openscad.org/downloads.html#openscad-web)
- [Customizer](https://www.thingiverse.com/customizer)
