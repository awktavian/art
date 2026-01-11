// Kagami Orb V3.1 — Diffuser Ring (VERIFIED DIMENSIONS)
// ========================================================
// Softens HD108 LED output at sphere equator
// Material: White resin (diffuse) or Frosted Clear
// Print: Form 4, 50μm layer height
//
// DESIGN NOTES:
// - Sits on top of LED mount ring
// - Diffuses light from 16× HD108 LEDs
// - Snap-fit tabs for easy assembly

/* [Diffuser Parameters] */
// Slightly larger than LED ring for light coverage
diffuser_outer_diameter = 58;     // Covers 55mm LED ring
diffuser_inner_diameter = 42;     // Inner opening
diffuser_height = 4;              // Low profile
diffuser_wall = 2;                // Wall thickness

/* [Interface with LED Ring] */
led_ring_outer = 55;              // Must match led_mount_ring.scad
snap_tab_count = 4;
snap_recess_width = 5.5;          // Slightly wider than LED ring tabs
snap_recess_depth = 2;

/* [Light Diffusion] */
diffuser_thickness = 1.5;         // Material thickness for diffusion
texture_depth = 0.3;              // Optional texture for better diffusion

// ============================================================
// MAIN MODULE
// ============================================================
module diffuser_ring() {
    difference() {
        union() {
            // Main ring body
            cylinder(h=diffuser_height, d=diffuser_outer_diameter, $fn=64);
        }
        
        // Inner opening
        translate([0, 0, -0.1])
            cylinder(h=diffuser_height + 0.2, d=diffuser_inner_diameter, $fn=64);
        
        // Snap tab recesses (to mate with LED ring)
        for (i = [0:snap_tab_count-1]) {
            rotate([0, 0, i * (360/snap_tab_count) + 45])
            translate([led_ring_outer/2 + 0.5, 0, -0.1])
                cube([6, snap_recess_width, snap_recess_depth + 0.1], center=true);
        }
        
        // Light diffusion texture (optional - small dimples)
        if (texture_depth > 0) {
            for (i = [0:31]) {
                rotate([0, 0, i * 11.25])
                translate([(diffuser_outer_diameter + diffuser_inner_diameter)/4, 0, diffuser_height - texture_depth])
                    sphere(r=0.8, $fn=8);
            }
        }
    }
}

// ============================================================
// RENDER
// ============================================================
diffuser_ring();

// ============================================================
// VERIFICATION
// ============================================================
echo("=== DIFFUSER RING VERIFICATION ===");
echo(str("Diffuser OD: ", diffuser_outer_diameter, "mm"));
echo(str("Diffuser ID: ", diffuser_inner_diameter, "mm"));
echo(str("Height: ", diffuser_height, "mm"));
echo(str("Covers LED ring: ", led_ring_outer, "mm"));
echo(str("Fits in 70mm internal? ", diffuser_outer_diameter < 70 ? "YES ✓" : "NO ✗"));
