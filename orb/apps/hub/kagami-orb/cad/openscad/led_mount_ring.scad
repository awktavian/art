// Kagami Orb V3.1 — LED Mount Ring (VERIFIED DIMENSIONS)
// ========================================================
// Holds 16× HD108 5050 LEDs at sphere equator
// Material: Grey Pro or Black PETG
// Print: Form 4, 50μm layer height
//
// VERIFIED SOURCES:
// - HD108 LED: 5.1 × 5.0 × 1.6mm (5050 package)
//   https://shine-leds.com/wp-content/uploads/2024/05/Specification-Datasheet-HD108.pdf

/* [HD108 LED Parameters - VERIFIED] */
// Source: HD108 datasheet
led_length = 5.1;                 // VERIFIED
led_width = 5.0;                  // VERIFIED (5050 = 5.0mm)
led_height = 1.6;                 // VERIFIED
led_count = 16;                   // Design spec
led_spacing_angle = 360 / led_count;  // 22.5° between LEDs

/* [Ring Parameters] */
ring_outer_diameter = 55;         // Fits at equator
ring_inner_diameter = 45;         // Inner opening
ring_height = 6;                  // Ring height
ring_wall = 2;                    // Wall thickness

/* [PCB Integration] */
pcb_thickness = 1.6;              // Standard PCB
pcb_slot_depth = 2;               // PCB sits in slot
led_ring_radius = 24;             // LED center radius

/* [Mounting] */
snap_tab_count = 4;               // Snap-fit to frame
snap_tab_width = 5;
snap_tab_height = 3;
snap_tab_protrusion = 1.5;

/* [Diffuser Interface] */
diffuser_slot_width = 2.5;        // Slot for diffuser ring
diffuser_slot_depth = 1.5;

// ============================================================
// DERIVED DIMENSIONS
// ============================================================
ring_mid_diameter = (ring_outer_diameter + ring_inner_diameter) / 2;

// ============================================================
// MAIN MODULE  
// ============================================================
module led_mount_ring() {
    difference() {
        union() {
            // Main ring body
            cylinder(h=ring_height, d=ring_outer_diameter, $fn=64);
            
            // Snap-fit tabs (outward)
            for (i = [0:snap_tab_count-1]) {
                rotate([0, 0, i * (360/snap_tab_count) + 45])
                translate([ring_outer_diameter/2, 0, ring_height/2])
                    snap_tab();
            }
        }
        
        // Inner opening
        translate([0, 0, -0.1])
            cylinder(h=ring_height + 0.2, d=ring_inner_diameter, $fn=64);
        
        // PCB slot (circular channel)
        translate([0, 0, ring_height - pcb_slot_depth])
        difference() {
            cylinder(h=pcb_slot_depth + 0.1, d=ring_outer_diameter - 4, $fn=64);
            cylinder(h=pcb_slot_depth + 0.1, d=ring_inner_diameter + 4, $fn=64);
        }
        
        // LED pockets (16×)
        for (i = [0:led_count-1]) {
            rotate([0, 0, i * led_spacing_angle])
            translate([led_ring_radius, 0, ring_height - pcb_thickness - led_height])
                led_pocket();
        }
        
        // Diffuser ring slot (top outer edge)
        translate([0, 0, ring_height - diffuser_slot_depth])
        difference() {
            cylinder(h=diffuser_slot_depth + 0.1, d=ring_outer_diameter + 0.2, $fn=64);
            cylinder(h=diffuser_slot_depth + 0.1, d=ring_outer_diameter - diffuser_slot_width*2, $fn=64);
        }
        
        // Wire channel (single entry point)
        translate([ring_outer_diameter/2 - 3, 0, ring_height/2])
            rotate([0, 90, 0])
            cylinder(h=10, d=4, center=true, $fn=16);
    }
}

// ============================================================
// LED POCKET
// ============================================================
module led_pocket() {
    // Pocket for HD108 5050 LED
    // Slightly oversized for solder tolerance
    cube([led_length + 0.3, led_width + 0.3, led_height + 1], center=true);
}

// ============================================================
// SNAP TAB
// ============================================================
module snap_tab() {
    // Snap-fit tab for frame attachment
    hull() {
        cube([snap_tab_protrusion * 2, snap_tab_width, snap_tab_height], center=true);
        translate([snap_tab_protrusion, 0, snap_tab_height/2])
            cube([0.5, snap_tab_width - 1, 0.5], center=true);
    }
}

// ============================================================
// RENDER
// ============================================================
led_mount_ring();

// ============================================================
// VERIFICATION
// ============================================================
echo("=== LED MOUNT RING VERIFICATION ===");
echo(str("Ring OD: ", ring_outer_diameter, "mm"));
echo(str("Ring ID: ", ring_inner_diameter, "mm"));
echo(str("LED count: ", led_count, " × HD108"));
echo(str("LED size (verified): ", led_length, " × ", led_width, " × ", led_height, "mm"));
echo(str("LED spacing: ", led_spacing_angle, "°"));
echo(str("Fits in 70mm internal? ", ring_outer_diameter < 70 ? "YES ✓" : "NO ✗"));
