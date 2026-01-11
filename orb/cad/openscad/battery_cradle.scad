// Kagami Orb — Battery Cradle
// Secures 3S Li-Po pack in bottom of sphere
// Material: Tough 2000
// Print: Form 4, 50μm layer height

/* [Battery Pocket] */
pocket_length = 102;          // Battery length + tolerance
pocket_width = 62;            // Battery width + tolerance
pocket_depth = 22;            // Battery depth + tolerance

/* [Cradle Parameters] */
wall_thickness = 2;           // Wall thickness
floor_thickness = 2;          // Floor thickness
corner_radius = 5;            // Corner radius

/* [Strap Slots] */
strap_slot_width = 15;        // Velcro strap width
strap_slot_length = 25;       // Slot length
strap_slot_offset = 20;       // Offset from center

/* [Mounting] */
mount_count = 4;              // Number of mount holes
mount_diameter = 3.2;         // M3 clearance
mount_offset = 10;            // Offset from pocket edge

/* [Wire Exit] */
wire_channel_width = 10;      // Wire channel width
wire_channel_depth = 8;       // Wire channel depth

$fn = 60;

// Pocket shape with rounded corners
module pocket_shape(length, width, height, radius) {
    hull() {
        for (x = [-1, 1]) {
            for (y = [-1, 1]) {
                translate([x * (length / 2 - radius), y * (width / 2 - radius), 0])
                    cylinder(r = radius, h = height);
            }
        }
    }
}

// Main cradle body
module cradle_body() {
    outer_length = pocket_length + wall_thickness * 2;
    outer_width = pocket_width + wall_thickness * 2;
    outer_depth = pocket_depth + floor_thickness;
    
    difference() {
        // Outer shell
        pocket_shape(outer_length, outer_width, outer_depth, corner_radius + wall_thickness);
        
        // Inner pocket
        translate([0, 0, floor_thickness])
            pocket_shape(pocket_length, pocket_width, pocket_depth + 1, corner_radius);
    }
}

// Velcro strap slots
module strap_slots() {
    slot_z = floor_thickness + pocket_depth / 2;
    
    for (x_offset = [-strap_slot_offset, strap_slot_offset]) {
        // Front slot
        translate([x_offset, pocket_width / 2 + wall_thickness - 1, slot_z])
            rotate([90, 0, 0])
                hull() {
                    translate([-strap_slot_length / 2, 0, 0])
                        cylinder(d = strap_slot_width, h = wall_thickness + 2);
                    translate([strap_slot_length / 2, 0, 0])
                        cylinder(d = strap_slot_width, h = wall_thickness + 2);
                }
        
        // Back slot
        translate([x_offset, -pocket_width / 2 - wall_thickness + 1, slot_z])
            rotate([90, 0, 0])
                hull() {
                    translate([-strap_slot_length / 2, 0, 0])
                        cylinder(d = strap_slot_width, h = wall_thickness + 2);
                    translate([strap_slot_length / 2, 0, 0])
                        cylinder(d = strap_slot_width, h = wall_thickness + 2);
                }
    }
}

// Mount holes
module mount_holes() {
    outer_length = pocket_length + wall_thickness * 2;
    outer_width = pocket_width + wall_thickness * 2;
    mount_z = -1;
    
    positions = [
        [-outer_length / 2 + mount_offset, -outer_width / 2 + mount_offset],
        [outer_length / 2 - mount_offset, -outer_width / 2 + mount_offset],
        [-outer_length / 2 + mount_offset, outer_width / 2 - mount_offset],
        [outer_length / 2 - mount_offset, outer_width / 2 - mount_offset]
    ];
    
    for (pos = positions) {
        translate([pos[0], pos[1], mount_z])
            cylinder(d = mount_diameter, h = floor_thickness + 2);
    }
}

// Wire exit channel
module wire_channel() {
    channel_z = floor_thickness;
    
    translate([pocket_length / 2 - wire_channel_width, 0, channel_z])
        cube([wire_channel_width + wall_thickness + 1, wire_channel_depth, pocket_depth / 2], center = true);
}

// Foam padding recesses
module foam_recesses() {
    recess_depth = 1;
    
    translate([0, 0, floor_thickness + pocket_depth - recess_depth])
        pocket_shape(pocket_length - 10, pocket_width - 10, recess_depth + 1, corner_radius - 2);
}

// Final assembly
module battery_cradle() {
    difference() {
        cradle_body();
        strap_slots();
        mount_holes();
        wire_channel();
        foam_recesses();
    }
}

// Render
battery_cradle();

// Reference dimensions
echo("Battery Cradle Dimensions:");
echo(str("  Pocket: ", pocket_length, "x", pocket_width, "x", pocket_depth, "mm"));
echo(str("  Outer: ", pocket_length + wall_thickness * 2, "x", pocket_width + wall_thickness * 2, "mm"));
echo(str("  Strap Slots: ", strap_slot_width, "mm wide"));
