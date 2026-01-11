// Kagami Orb — Resonant Coil Mount
// Positions resonant receiver coil at bottom of orb
// Material: Tough 2000 (SLA) or PETG (FDM)
// Print: Form 4 Tough 2000, 50μm OR FDM 0.2mm

/* [Mount Parameters] */
mount_diameter = 85;          // Matches 80mm Litz coil
mount_height = 5;             // Platform height
wall_thickness = 2;           // Wall thickness

/* [Coil Recess] */
coil_diameter = 80;           // Litz coil diameter
coil_depth = 3;               // Coil recess depth
coil_wire_channel = 5;        // Wire exit channel width

/* [Alignment] */
alignment_pin_count = 3;      // Number of alignment pins
alignment_pin_diameter = 3;   // Pin diameter
alignment_pin_height = 2;     // Pin height above surface

/* [Mounting] */
mount_hole_count = 4;
mount_hole_diameter = 3.2;    // M3 clearance
mount_hole_radius = 38;       // Radius from center

$fn = 100;

module coil_mount() {
    difference() {
        union() {
            // Main platform
            cylinder(d = mount_diameter, h = mount_height);
            
            // Alignment pins
            for (i = [0:alignment_pin_count-1]) {
                angle = i * (360 / alignment_pin_count);
                rotate([0, 0, angle])
                    translate([coil_diameter/2 - 5, 0, mount_height])
                        cylinder(d = alignment_pin_diameter, h = alignment_pin_height);
            }
        }
        
        // Coil recess
        translate([0, 0, mount_height - coil_depth])
            cylinder(d = coil_diameter + 1, h = coil_depth + 0.5);
        
        // Center cutout for thermal path
        translate([0, 0, -0.5])
            cylinder(d = coil_diameter - 20, h = mount_height + 1);
        
        // Wire channel
        translate([coil_diameter/2 - 5, 0, mount_height - coil_depth - 0.5])
            cube([15, coil_wire_channel, coil_depth + 1], center = true);
        
        // Mount holes
        for (i = [0:mount_hole_count-1]) {
            angle = i * (360 / mount_hole_count) + 45;
            rotate([0, 0, angle])
                translate([mount_hole_radius, 0, -0.5])
                    cylinder(d = mount_hole_diameter, h = mount_height + 1);
        }
    }
}

// Render
coil_mount();

echo("Resonant Coil Mount:");
echo(str("  Diameter: ", mount_diameter, "mm"));
echo(str("  Height: ", mount_height, "mm"));
echo(str("  Coil recess: ", coil_diameter, "mm x ", coil_depth, "mm"));
echo("Print Settings:");
echo("  SLA: Tough 2000, 50μm, minimal supports");
echo("  FDM: PETG, 0.2mm, 40% infill");
