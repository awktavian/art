// Kagami Orb — LED Mount Ring
// Holds SK6812 24-LED ring at sphere equator
// Material: Grey Pro
// Print: Form 4, 25μm layer height

/* [Ring Parameters] */
inner_diameter = 75;          // Inner diameter
outer_diameter = 85;          // Outer diameter
ring_height = 8;              // Total height

/* [LED Groove] */
led_groove_id = 68;           // LED ring inner diameter
led_groove_od = 74;           // LED ring outer diameter  
led_groove_depth = 2;         // Groove depth for PCB

/* [Diffuser Slot] */
diffuser_slot_width = 3;      // Diffuser slot width
diffuser_slot_depth = 4;      // Diffuser slot depth

/* [Snap Tabs] */
snap_tab_count = 6;           // Number of snap tabs
snap_tab_width = 6;           // Tab width
snap_tab_length = 8;          // Tab length
snap_tab_height = 3;          // Tab height

/* [Cable Exit] */
cable_notch_width = 8;        // Cable exit notch width
cable_notch_depth = 5;        // Cable exit notch depth

$fn = 120;

// Main ring body
module ring_body() {
    difference() {
        // Outer ring
        cylinder(d = outer_diameter, h = ring_height);
        
        // Inner cutout
        translate([0, 0, -1])
            cylinder(d = inner_diameter, h = ring_height + 2);
    }
}

// LED PCB groove
module led_groove() {
    groove_z = (ring_height - led_groove_depth) / 2;
    
    translate([0, 0, groove_z])
        difference() {
            cylinder(d = led_groove_od + 1, h = led_groove_depth + 0.5);
            translate([0, 0, -1])
                cylinder(d = led_groove_id - 1, h = led_groove_depth + 2);
        }
}

// Diffuser slot above LEDs
module diffuser_slot() {
    slot_z = ring_height - diffuser_slot_depth;
    slot_mid_d = (inner_diameter + outer_diameter) / 2;
    
    translate([0, 0, slot_z])
        difference() {
            cylinder(d = slot_mid_d + diffuser_slot_width / 2, h = diffuser_slot_depth + 1);
            translate([0, 0, -1])
                cylinder(d = slot_mid_d - diffuser_slot_width / 2, h = diffuser_slot_depth + 2);
        }
}

// Snap-fit tabs for frame attachment
module snap_tabs() {
    tab_radius = outer_diameter / 2;
    
    for (i = [0 : snap_tab_count - 1]) {
        angle = i * (360 / snap_tab_count);
        rotate([0, 0, angle])
            translate([tab_radius - 1, 0, ring_height / 2]) {
                // Tab body
                difference() {
                    translate([0, -snap_tab_width / 2, -snap_tab_height / 2])
                        cube([snap_tab_length, snap_tab_width, snap_tab_height]);
                    
                    // Snap-fit ramp
                    translate([snap_tab_length - 2, -snap_tab_width / 2 - 1, snap_tab_height / 2 - 1])
                        rotate([0, 30, 0])
                            cube([4, snap_tab_width + 2, 3]);
                }
            }
    }
}

// Cable exit notch
module cable_notch() {
    notch_radius = (inner_diameter + outer_diameter) / 4;
    
    translate([notch_radius, 0, -1])
        cube([cable_notch_depth, cable_notch_width, ring_height + 2], center = true);
}

// Final assembly
module led_mount_ring() {
    difference() {
        union() {
            ring_body();
            snap_tabs();
        }
        led_groove();
        diffuser_slot();
        cable_notch();
    }
}

// Render
led_mount_ring();

// Reference dimensions
echo("LED Mount Ring Dimensions:");
echo(str("  Inner Diameter: ", inner_diameter, "mm"));
echo(str("  Outer Diameter: ", outer_diameter, "mm"));
echo(str("  Height: ", ring_height, "mm"));
echo(str("  LED Groove: ", led_groove_id, "-", led_groove_od, "mm"));
