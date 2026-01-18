// Kagami Orb V3.1 — Display Mount (VERIFIED DIMENSIONS)
// ========================================================
// Holds 1.39" round AMOLED at top of sphere
// Material: Grey Pro (dimensional stability)
// Print: Form 4, 25μm layer height (precision)
//
// SOURCES:
// - 1.39" AMOLED: King Tech Display datasheet
//   https://www.kingtechdisplay.com
// - IMX989 Module: SincereFirst 26×26×9.4mm
//   https://sincerefirst.en.made-in-china.com

/* [Display Parameters - 1.39" Round AMOLED 454×454] */
// VERIFIED: King Tech Display datasheet
// Module: 38.83mm (H) × 38.21mm (W) × 0.68mm (T)
// Active: 35.41mm diameter
display_module_height = 38.83;    // Verified dimension
display_module_width = 38.21;     // Verified dimension  
display_module_thickness = 0.68;  // Verified dimension
display_active_diameter = 35.41;  // Verified dimension

/* [Camera Integration - IMX989 Behind Display] */
// VERIFIED: SincereFirst module dimensions
// Module: 26mm × 26mm × 9.4mm
camera_module_size = 26;          // Verified: 26mm square
camera_module_depth = 9.4;        // Verified: includes lens
camera_aperture = 6;              // Pupil hole diameter

/* [Mount Parameters] */
mount_outer_diameter = 45;        // Fits inside 65mm frame
mount_height = 12;                // Depth for display + camera
wall_thickness = 2.5;             // Structural minimum
mount_tolerance = 0.15;           // SLA print tolerance

/* [Retention Features] */
clip_count = 4;                   // Retention clips
clip_width = 3;
clip_depth = 1.5;
screw_hole_diameter = 2.2;        // M2 screws
screw_count = 3;

/* [Derived Dimensions] */
// Display recess (add tolerance)
display_recess_diameter = display_module_height + mount_tolerance * 2;
display_recess_depth = display_module_thickness + 0.3;

// Camera recess (centered)
camera_recess_size = camera_module_size + mount_tolerance * 2;
camera_recess_depth = camera_module_depth + 0.5;

// ============================================================
// MAIN MODULE
// ============================================================
module display_mount() {
    difference() {
        union() {
            // Main body - cylindrical
            cylinder(h=mount_height, d=mount_outer_diameter, $fn=64);
            
            // Retention clips
            for (i = [0:clip_count-1]) {
                rotate([0, 0, i * (360/clip_count)])
                translate([mount_outer_diameter/2 - 1, 0, mount_height - 3])
                    retention_clip();
            }
        }
        
        // Display recess (top) - rectangular for module
        translate([0, 0, mount_height - display_recess_depth])
        linear_extrude(display_recess_depth + 0.1)
            rounded_square([display_module_width + mount_tolerance*2, 
                           display_module_height + mount_tolerance*2], 
                          r=2);
        
        // Display viewing aperture (through)
        translate([0, 0, -0.1])
            cylinder(h=mount_height + 0.2, d=display_active_diameter - 1, $fn=64);
        
        // Camera recess (below display)
        translate([0, 0, mount_height - display_recess_depth - camera_recess_depth])
        linear_extrude(camera_recess_depth + 0.1)
            square([camera_recess_size, camera_recess_size], center=true);
        
        // Camera aperture (pupil) - through center
        translate([0, 0, -0.1])
            cylinder(h=mount_height + 0.2, d=camera_aperture, $fn=32);
        
        // Flex cable channel
        translate([0, display_module_height/2 + 2, mount_height/2])
            cube([12, 10, mount_height + 0.2], center=true);
        
        // M2 screw holes
        for (i = [0:screw_count-1]) {
            angle = i * (360/screw_count) + 60;  // Offset from clips
            rotate([0, 0, angle])
            translate([mount_outer_diameter/2 - 4, 0, -0.1])
                cylinder(h=mount_height + 0.2, d=screw_hole_diameter, $fn=16);
        }
    }
}

// ============================================================
// HELPER MODULES
// ============================================================
module retention_clip() {
    // Snap-fit clip for display retention
    hull() {
        cube([clip_width, clip_depth, 0.1], center=true);
        translate([0, clip_depth/2, 2])
            cube([clip_width, 0.5, 0.1], center=true);
    }
}

module rounded_square(size, r=2) {
    // Rounded rectangle for display recess
    offset(r=r) offset(r=-r)
        square(size, center=true);
}

// ============================================================
// RENDER
// ============================================================
display_mount();

// ============================================================
// VERIFICATION ANNOTATIONS
// ============================================================
echo("=== DISPLAY MOUNT VERIFICATION ===");
echo(str("Display module: ", display_module_width, " × ", display_module_height, " × ", display_module_thickness, "mm"));
echo(str("Display active: ", display_active_diameter, "mm diameter"));
echo(str("Camera module: ", camera_module_size, " × ", camera_module_size, " × ", camera_module_depth, "mm"));
echo(str("Mount outer: ", mount_outer_diameter, "mm"));
echo(str("Mount height: ", mount_height, "mm"));
echo(str("Fits in 65mm frame? ", mount_outer_diameter < 65 ? "YES ✓" : "NO ✗"));
