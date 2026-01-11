// Kagami Orb — CM4 Mount Bracket
// Heat sink mount and CM4 alignment
// Material: Grey Pro (SLA) or PETG (FDM)
// Print: Form 4 Grey Pro, 50μm OR FDM 0.2mm

/* [Bracket Parameters] */
bracket_length = 55;          // Length (CM4 + clearance)
bracket_width = 45;           // Width (CM4 + clearance)
bracket_height = 3;           // Base plate thickness

/* [Heatsink Contact] */
heatsink_size = 40;           // Heatsink contact area
heatsink_cutout_depth = 1;    // Thermal pad recess

/* [Mounting Holes] */
// CM4 mounting pattern: 58mm x 45mm
hole_spacing_x = 58;
hole_spacing_y = 45;
hole_diameter = 2.7;          // M2.5 clearance
standoff_height = 5;          // Standoff height
standoff_diameter = 6;        // Standoff OD

/* [Airflow] */
vent_slot_width = 3;
vent_slot_count = 4;

$fn = 60;

module mounting_standoff() {
    difference() {
        cylinder(d = standoff_diameter, h = standoff_height);
        translate([0, 0, -0.5])
            cylinder(d = hole_diameter, h = standoff_height + 1);
    }
}

module cm4_bracket() {
    difference() {
        union() {
            // Base plate
            hull() {
                for (x = [-1, 1]) {
                    for (y = [-1, 1]) {
                        translate([x * (bracket_length/2 - 3), y * (bracket_width/2 - 3), 0])
                            cylinder(r = 3, h = bracket_height);
                    }
                }
            }
            
            // Mounting standoffs
            standoff_positions = [
                [-hole_spacing_x/2, -hole_spacing_y/2],
                [hole_spacing_x/2, -hole_spacing_y/2],
                [-hole_spacing_x/2, hole_spacing_y/2],
                [hole_spacing_x/2, hole_spacing_y/2]
            ];
            
            for (pos = standoff_positions) {
                translate([pos[0], pos[1], bracket_height])
                    mounting_standoff();
            }
        }
        
        // Heatsink thermal contact recess
        translate([0, 0, bracket_height - heatsink_cutout_depth])
            cube([heatsink_size, heatsink_size, heatsink_cutout_depth + 0.5], center = true);
        
        // Center vent hole
        translate([0, 0, -0.5])
            cylinder(d = heatsink_size - 10, h = bracket_height + 1);
        
        // Vent slots
        for (i = [0:vent_slot_count-1]) {
            angle = i * (360 / vent_slot_count) + 45;
            rotate([0, 0, angle])
                translate([heatsink_size/2 + 5, 0, -0.5])
                    hull() {
                        cylinder(d = vent_slot_width, h = bracket_height + 1);
                        translate([8, 0, 0])
                            cylinder(d = vent_slot_width, h = bracket_height + 1);
                    }
        }
    }
}

// Render
cm4_bracket();

echo("CM4 Bracket:");
echo(str("  Size: ", bracket_length, "x", bracket_width, "x", bracket_height + standoff_height, "mm"));
echo(str("  Hole pattern: ", hole_spacing_x, "x", hole_spacing_y, "mm"));
echo("Print Settings:");
echo("  SLA: Grey Pro, 50μm, minimal supports");
echo("  FDM: PETG, 0.2mm, 30% infill, supports needed");
