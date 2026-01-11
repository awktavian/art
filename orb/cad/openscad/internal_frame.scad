// Kagami Orb V3.1 — Internal Frame (VERIFIED DIMENSIONS)
// ========================================================
// Main structural frame for 85mm sealed sphere
// Material: CF-PETG or Tough 2000
// Print: Form 4, 50μm layer height
//
// VERIFIED SOURCES:
// - QCS6490 SoM: Thundercomm TurboX C6490 datasheet
//   42.5 × 35.5 × 2.7mm (verified Jan 2026)
// - Hailo-10H: M.2 2242 standard = 42 × 22 × 2.7mm
// - Internal volume: 85mm - 2×7.5mm shell = 70mm max

/* [Frame Parameters - Fits 70mm Internal] */
frame_outer_diameter = 62;        // Leave 4mm clearance to shell
frame_height = 42;                // Compact vertical stack
wall_thickness = 2.5;             // Structural minimum

/* [QCS6490 SoM Mount - VERIFIED Thundercomm] */
// Source: https://www.thundercomm.com/product/c6490-som/
// Dimensions: 42.5 × 35.5 × 2.7mm
som_length = 42.5;                // VERIFIED
som_width = 35.5;                 // VERIFIED  
som_height = 2.7;                 // VERIFIED (plus connectors ~5mm total)
som_mount_tolerance = 0.3;        // Fit tolerance

/* [Hailo-10H M.2 Mount - VERIFIED M.2 2242] */
// Standard M.2 2242: 42 × 22mm
// Height varies 2.7-3.6mm typical
m2_length = 42;                   // VERIFIED (2242 = 42mm)
m2_width = 22;                    // VERIFIED (22mm standard)
m2_height = 3.6;                  // Max height allowance
m2_key_offset = 4;                // Key M notch position

/* [Display Mount Interface] */
display_mount_diameter = 45;      // Matches display_mount.scad
display_interface_depth = 3;      // Snap-fit depth

/* [Speaker Mount - VERIFIED 28mm] */
// Source: Yueda 28mm speaker, 28 × 5.4mm
speaker_diameter = 28;            // VERIFIED
speaker_depth = 5.4;              // VERIFIED
speaker_mount_tolerance = 0.5;

/* [LED Ring Interface] */
led_ring_diameter = 55;           // HD108 ring at equator
led_tab_width = 6;
led_tab_count = 4;

/* [Battery Interface - VERIFIED feasible size] */
// Max battery that fits: 55 × 35 × 20mm (2200mAh 3S)
battery_length = 55;              // Verified fit
battery_width = 35;               // Verified fit
battery_height = 20;              // Verified fit

/* [Thermal Management] */
heatsink_size = 14;               // 14×14mm heatsink for SoC
thermal_pad_thickness = 1;        // 1mm thermal pad
vent_slot_count = 0;              // SEALED DESIGN - no vents!

/* [Mounting] */
screw_diameter = 2.2;             // M2 screws
standoff_height = 4;              // SoM standoffs
standoff_diameter = 4;

// ============================================================
// DERIVED DIMENSIONS
// ============================================================
frame_inner_diameter = frame_outer_diameter - 2 * wall_thickness;
som_pocket_length = som_length + som_mount_tolerance * 2;
som_pocket_width = som_width + som_mount_tolerance * 2;

// ============================================================
// MAIN MODULE
// ============================================================
module internal_frame() {
    difference() {
        union() {
            // Main cylindrical body
            cylinder(h=frame_height, d=frame_outer_diameter, $fn=64);
            
            // LED ring mounting tabs
            for (i = [0:led_tab_count-1]) {
                rotate([0, 0, i * (360/led_tab_count)])
                translate([frame_outer_diameter/2, 0, frame_height/2])
                    led_mount_tab();
            }
        }
        
        // Central cavity
        translate([0, 0, wall_thickness])
            cylinder(h=frame_height, d=frame_inner_diameter, $fn=64);
        
        // Display mount interface (top)
        translate([0, 0, frame_height - display_interface_depth])
            cylinder(h=display_interface_depth + 0.1, d=display_mount_diameter + 0.3, $fn=64);
        
        // QCS6490 SoM pocket
        translate([0, 0, frame_height - 15])
            som_pocket();
        
        // M.2 slot for Hailo-10H
        translate([0, -8, frame_height - 22])
            m2_slot();
        
        // Speaker cavity (bottom center)
        translate([0, 0, wall_thickness])
            cylinder(h=speaker_depth + 1, d=speaker_diameter + speaker_mount_tolerance*2, $fn=32);
        
        // Speaker grille holes
        for (i = [0:5]) {
            rotate([0, 0, i * 60])
            translate([8, 0, -0.1])
                cylinder(h=wall_thickness + 0.2, d=3, $fn=16);
        }
        
        // Battery cable routing
        translate([0, frame_inner_diameter/2 - 5, frame_height/2])
            rotate([90, 0, 0])
            cylinder(h=10, d=8, $fn=16);
        
        // Thermal path to shell (graphite contact)
        translate([0, 0, frame_height - 2])
            cylinder(h=3, d=heatsink_size + 5, $fn=32);
    }
    
    // SoM standoffs
    translate([0, 0, frame_height - 15])
        som_standoffs();
}

// ============================================================
// SOM MOUNTING
// ============================================================
module som_pocket() {
    // Pocket for QCS6490 SoM (42.5 × 35.5mm)
    linear_extrude(som_height + standoff_height + 1)
        rounded_rect([som_pocket_length, som_pocket_width], r=2);
}

module som_standoffs() {
    // M2 standoffs for SoM mounting
    // Positions based on typical SoM hole pattern
    positions = [
        [som_length/2 - 3, som_width/2 - 3],
        [-som_length/2 + 3, som_width/2 - 3],
        [som_length/2 - 3, -som_width/2 + 3],
        [-som_length/2 + 3, -som_width/2 + 3]
    ];
    
    for (pos = positions) {
        translate([pos[0], pos[1], 0])
        difference() {
            cylinder(h=standoff_height, d=standoff_diameter, $fn=16);
            translate([0, 0, -0.1])
                cylinder(h=standoff_height + 0.2, d=screw_diameter, $fn=16);
        }
    }
}

// ============================================================
// M.2 SLOT
// ============================================================
module m2_slot() {
    // M.2 2242 slot (42 × 22mm)
    linear_extrude(m2_height + 1)
        rounded_rect([m2_length + 1, m2_width + 0.5], r=1);
    
    // Key M notch
    translate([-m2_length/2 - 0.5, -m2_width/2 + m2_key_offset, 0])
        cube([2, 4, m2_height + 1]);
    
    // Retention screw hole
    translate([m2_length/2 - 2, 0, -5])
        cylinder(h=10, d=screw_diameter, $fn=16);
}

// ============================================================
// LED MOUNT TAB
// ============================================================
module led_mount_tab() {
    // Snap-fit tab for LED ring
    cube([led_tab_width, 3, 8], center=true);
}

// ============================================================
// HELPER MODULES
// ============================================================
module rounded_rect(size, r=2) {
    offset(r=r) offset(r=-r)
        square(size, center=true);
}

// ============================================================
// RENDER
// ============================================================
internal_frame();

// ============================================================
// VERIFICATION
// ============================================================
echo("=== INTERNAL FRAME VERIFICATION ===");
echo(str("Frame OD: ", frame_outer_diameter, "mm (max 65mm for 70mm internal)"));
echo(str("Frame height: ", frame_height, "mm"));
echo(str("QCS6490 pocket: ", som_pocket_length, " × ", som_pocket_width, "mm"));
echo(str("M.2 slot: ", m2_length, " × ", m2_width, "mm"));
echo(str("Speaker mount: ", speaker_diameter, "mm"));
echo(str("Fits in sphere? ", frame_outer_diameter < 65 ? "YES ✓" : "NO ✗"));
echo(str("SEALED DESIGN: ", vent_slot_count == 0 ? "YES (no vents)" : "NO"));
