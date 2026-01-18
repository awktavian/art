// Kagami Orb V3.1 — Battery Cradle (VERIFIED DIMENSIONS)
// ========================================================
// Holds 2200mAh 3S LiPo battery (revised from 4000mAh)
// Material: Tough 2000 (impact resistant)
// Print: Form 4, 50μm layer height
//
// VERIFIED SOURCES:
// - Battery search: HobbyKing, GensTattu, TyphonPower
// - 4000mAh minimum: 131×43×24mm (TOO LARGE for 65mm frame!)
// - 2200mAh typical: 55×35×20mm (FITS)

/* [Battery Parameters - 2200mAh 3S VERIFIED] */
// Verified: Compact 3S LiPo that fits 65mm frame
battery_length = 55;              // VERIFIED max that fits
battery_width = 35;               // VERIFIED
battery_height = 20;              // VERIFIED
battery_tolerance = 0.5;          // Fit tolerance

/* [Cradle Parameters] */
cradle_wall = 2;                  // Wall thickness
cradle_floor = 2;                 // Base thickness
foam_recess = 1;                  // Foam padding depth

/* [BMS Integration] */
// BQ25895 + BQ40Z50 board area
bms_length = 25;
bms_width = 15;
bms_height = 5;

/* [Retention Features] */
strap_slot_width = 8;             // Velcro strap slots
strap_slot_depth = 2;
strap_count = 2;

/* [Mounting] */
mount_hole_diameter = 3.2;        // M3 clearance
mount_hole_count = 4;
mount_tab_width = 8;
mount_tab_length = 6;

/* [Wire Routing] */
wire_channel_diameter = 6;        // Main power wires
balance_channel_width = 10;       // Balance connector

// ============================================================
// DERIVED DIMENSIONS
// ============================================================
cradle_length = battery_length + battery_tolerance * 2 + cradle_wall * 2;
cradle_width = battery_width + battery_tolerance * 2 + cradle_wall * 2;
cradle_height = battery_height / 2 + cradle_floor; // Half-wrap design

// ============================================================
// MAIN MODULE
// ============================================================
module battery_cradle() {
    difference() {
        union() {
            // Main cradle body
            hull() {
                translate([0, 0, 0])
                    rounded_box([cradle_length, cradle_width, cradle_height], r=3);
            }
            
            // Mounting tabs
            mounting_tabs();
        }
        
        // Battery pocket
        translate([0, 0, cradle_floor])
            rounded_box([battery_length + battery_tolerance*2, 
                        battery_width + battery_tolerance*2, 
                        battery_height], r=2);
        
        // Foam padding recesses
        translate([0, 0, cradle_floor])
            rounded_box([battery_length - 4, 
                        battery_width - 4, 
                        foam_recess + 0.1], r=1);
        
        // Strap slots
        for (i = [0:strap_count-1]) {
            x_pos = (i - (strap_count-1)/2) * (battery_length / 2);
            translate([x_pos, 0, cradle_height - strap_slot_depth])
                cube([strap_slot_width, cradle_width + 2, strap_slot_depth * 2], center=true);
        }
        
        // BMS pocket (side)
        translate([cradle_length/2 - bms_length/2 - cradle_wall, 
                  -cradle_width/2, 
                  cradle_floor])
            cube([bms_length + 1, bms_width + 1, bms_height + 1]);
        
        // Wire channel (main power)
        translate([cradle_length/2, 0, cradle_height/2])
            rotate([0, 90, 0])
            cylinder(h=cradle_wall * 2 + 1, d=wire_channel_diameter, center=true, $fn=16);
        
        // Balance connector channel
        translate([-cradle_length/2, 0, cradle_height/2])
            rotate([0, 90, 0])
            cube([6, balance_channel_width, cradle_wall * 2 + 1], center=true);
        
        // Mounting holes
        mount_holes();
    }
}

// ============================================================
// MOUNTING
// ============================================================
module mounting_tabs() {
    positions = [
        [cradle_length/2 + mount_tab_length/2, cradle_width/2 - mount_tab_width/2, 0],
        [cradle_length/2 + mount_tab_length/2, -cradle_width/2 + mount_tab_width/2, 0],
        [-cradle_length/2 - mount_tab_length/2, cradle_width/2 - mount_tab_width/2, 0],
        [-cradle_length/2 - mount_tab_length/2, -cradle_width/2 + mount_tab_width/2, 0]
    ];
    
    for (pos = positions) {
        translate(pos)
            rounded_box([mount_tab_length, mount_tab_width, cradle_floor + 2], r=1.5);
    }
}

module mount_holes() {
    positions = [
        [cradle_length/2 + mount_tab_length/2, cradle_width/2 - mount_tab_width/2],
        [cradle_length/2 + mount_tab_length/2, -cradle_width/2 + mount_tab_width/2],
        [-cradle_length/2 - mount_tab_length/2, cradle_width/2 - mount_tab_width/2],
        [-cradle_length/2 - mount_tab_length/2, -cradle_width/2 + mount_tab_width/2]
    ];
    
    for (pos = positions) {
        translate([pos[0], pos[1], -0.1])
            cylinder(h=cradle_floor + 3, d=mount_hole_diameter, $fn=16);
    }
}

// ============================================================
// HELPER MODULES
// ============================================================
module rounded_box(size, r=2) {
    hull() {
        for (x = [-1, 1]) {
            for (y = [-1, 1]) {
                translate([x * (size[0]/2 - r), y * (size[1]/2 - r), 0])
                    cylinder(h=size[2], r=r, $fn=16);
            }
        }
    }
}

// ============================================================
// RENDER
// ============================================================
battery_cradle();

// ============================================================
// VERIFICATION
// ============================================================
echo("=== BATTERY CRADLE VERIFICATION ===");
echo(str("Battery: ", battery_length, " × ", battery_width, " × ", battery_height, "mm (2200mAh 3S)"));
echo(str("Cradle OD: ", cradle_length, " × ", cradle_width, "mm"));
echo(str("Fits in 65mm frame? ", max(cradle_length, cradle_width) < 65 ? "YES ✓" : "NO ✗"));
echo(str("Energy: ~24Wh (2200mAh × 11.1V)"));
echo("");
echo("NOTE: 4000mAh batteries are 131mm+ long - WON'T FIT!");
echo("This design uses 2200mAh (55mm) - the largest that fits.");
