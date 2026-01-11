// Kagami Orb — Diffuser Ring
// Softens LED hotspots for infinity mirror effect
// Material: White resin (SLA) or White PETG (FDM)
// Print: Form 4 White resin, 50μm OR FDM 0.2mm

/* [Ring Parameters] */
inner_diameter = 70;          // Inner diameter
outer_diameter = 80;          // Outer diameter
ring_height = 3;              // Ring height

/* [Surface Finish] */
// For SLA: use frosted/matte finish
// For FDM: print with 0% infill for light diffusion

$fn = 180;  // High resolution for smooth curves

module diffuser_ring() {
    difference() {
        cylinder(d = outer_diameter, h = ring_height);
        translate([0, 0, -0.5])
            cylinder(d = inner_diameter, h = ring_height + 1);
    }
}

// Render
diffuser_ring();

echo("Diffuser Ring:");
echo(str("  ID: ", inner_diameter, "mm"));
echo(str("  OD: ", outer_diameter, "mm"));
echo(str("  Height: ", ring_height, "mm"));
echo("Print Settings:");
echo("  SLA: White resin, 50μm, matte finish");
echo("  FDM: White PETG, 0.2mm, 0% infill, 2 walls");
