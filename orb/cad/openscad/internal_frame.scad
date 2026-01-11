// Kagami Orb — Internal Frame
// Main structural element holding all electronics
// Material: CF-PETG or Tough 2000
// Print: Form 4, 50μm layer height

/* [Frame Parameters] */
frame_diameter = 95;          // Overall diameter
frame_height = 60;            // Overall height
wall_thickness = 3;           // Wall thickness

/* [CM4 Platform] */
cm4_platform_length = 55;     // CM4 cutout length
cm4_platform_width = 40;      // CM4 cutout width
cm4_standoff_diameter = 5;    // M2.5 standoff hole
cm4_standoff_height = 8;      // Standoff height

/* [LED Mount Tabs] */
led_tab_count = 6;            // Number of tabs (60° spacing)
led_tab_width = 8;            // Tab width
led_tab_depth = 5;            // Tab depth
led_tab_height = 10;          // Tab height

/* [Battery Mount] */
battery_mount_count = 4;      // Number of mount points
battery_mount_diameter = 4;   // M3 insert diameter

/* [Tolerances] */
tolerance = 0.2;              // General print tolerance

$fn = 100;                    // Circle resolution

// Main frame body
module frame_body() {
    difference() {
        // Outer shell - slightly tapered for aesthetics
        hull() {
            translate([0, 0, frame_height - 5])
                cylinder(d = frame_diameter - 4, h = 5);
            cylinder(d = frame_diameter, h = frame_height - 5);
        }
        
        // Inner cavity
        translate([0, 0, wall_thickness])
            hull() {
                translate([0, 0, frame_height - wall_thickness - 8])
                    cylinder(d = frame_diameter - wall_thickness * 2 - 4, h = 5);
                cylinder(d = frame_diameter - wall_thickness * 2, h = frame_height - wall_thickness * 2 - 5);
            }
    }
}

// CM4 platform
module cm4_platform() {
    platform_z = frame_height / 2;
    
    // Central platform
    translate([0, 0, platform_z - 2])
        cube([cm4_platform_length, cm4_platform_width, 4], center = true);
    
    // Standoffs for CM4 mounting
    standoff_positions = [
        [-cm4_platform_length/2 + 5, -cm4_platform_width/2 + 5],
        [cm4_platform_length/2 - 5, -cm4_platform_width/2 + 5],
        [-cm4_platform_length/2 + 5, cm4_platform_width/2 - 5],
        [cm4_platform_length/2 - 5, cm4_platform_width/2 - 5]
    ];
    
    for (pos = standoff_positions) {
        translate([pos[0], pos[1], platform_z])
            difference() {
                cylinder(d = cm4_standoff_diameter + 3, h = cm4_standoff_height);
                cylinder(d = 2.2, h = cm4_standoff_height + 1); // M2.5 insert hole
            }
    }
}

// LED mount tabs around equator
module led_mount_tabs() {
    tab_z = frame_height / 2;
    tab_radius = frame_diameter / 2 - wall_thickness / 2;
    
    for (i = [0 : led_tab_count - 1]) {
        angle = i * (360 / led_tab_count);
        rotate([0, 0, angle])
            translate([tab_radius, 0, tab_z - led_tab_height / 2])
                difference() {
                    cube([led_tab_depth, led_tab_width, led_tab_height], center = true);
                    // Snap-fit groove
                    translate([led_tab_depth / 2 - 1, 0, 0])
                        cube([2, led_tab_width - 2, led_tab_height - 4], center = true);
                }
    }
}

// Battery cradle mount points
module battery_mounts() {
    mount_z = wall_thickness + 5;
    mount_radius = frame_diameter / 2 - 15;
    
    for (i = [0 : battery_mount_count - 1]) {
        angle = i * (360 / battery_mount_count) + 45;
        rotate([0, 0, angle])
            translate([mount_radius, 0, mount_z])
                difference() {
                    cylinder(d = battery_mount_diameter + 4, h = 10);
                    cylinder(d = battery_mount_diameter, h = 11); // M3 insert
                }
    }
}

// Ventilation slots
module ventilation_slots() {
    slot_count = 12;
    slot_z = frame_height - 15;
    slot_radius = frame_diameter / 2 - wall_thickness / 2;
    
    for (i = [0 : slot_count - 1]) {
        angle = i * (360 / slot_count);
        rotate([0, 0, angle])
            translate([slot_radius, 0, slot_z])
                rotate([0, 90, 0])
                    hull() {
                        cylinder(d = 3, h = wall_thickness + 2, center = true);
                        translate([0, 0, 8])
                            cylinder(d = 3, h = wall_thickness + 2, center = true);
                    }
    }
}

// Cable routing channels
module cable_channels() {
    channel_width = 5;
    channel_depth = 2;
    
    // Main channel from bottom to CM4
    translate([0, frame_diameter / 2 - wall_thickness - channel_depth, 0])
        cube([channel_width, channel_depth * 2, frame_height / 2], center = false);
}

// Final assembly
module internal_frame() {
    difference() {
        union() {
            frame_body();
            cm4_platform();
            led_mount_tabs();
            battery_mounts();
        }
        ventilation_slots();
        cable_channels();
    }
}

// Render
internal_frame();

// Assembly reference dimensions
echo("Internal Frame Dimensions:");
echo(str("  Diameter: ", frame_diameter, "mm"));
echo(str("  Height: ", frame_height, "mm"));
echo(str("  CM4 Platform: ", cm4_platform_length, "x", cm4_platform_width, "mm"));
echo(str("  LED Tabs: ", led_tab_count, " @ ", led_tab_width, "mm width"));
