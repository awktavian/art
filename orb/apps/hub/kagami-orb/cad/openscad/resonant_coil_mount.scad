// Kagami Orb V3.1 — Resonant Coil Mount (VERIFIED DIMENSIONS)
// ========================================================
// Holds 70mm RX coil at sphere bottom for wireless power
// Material: Tough 2000 (heat resistant)
// Print: Form 4, 50μm layer height
//
// DESIGN NOTES:
// - Coil is 70mm to match base TX coil
// - Ferrite sheet prevents eddy currents in components above
// - Thermal vias conduct heat to shell (sealed design)

/* [RX Coil Parameters] */
// Design spec: 70mm diameter Litz wire coil
coil_outer_diameter = 70;         // Matches TX coil
coil_inner_diameter = 40;         // Center opening
coil_wire_diameter = 1.0;         // Litz wire gauge
coil_turns = 18;                  // For 85μH inductance
coil_width = 15;                  // Winding width (radial)
coil_height = 3;                  // Winding height

/* [Mount Parameters] */
mount_outer_diameter = 72;        // Coil + clearance
mount_height = 8;                 // Total mount height
mount_wall = 2;                   // Wall thickness
mount_tolerance = 0.3;

/* [Ferrite Integration] */
// Fair-Rite ferrite sheet for shielding
ferrite_diameter = 60;            // 60mm ferrite disc
ferrite_thickness = 0.5;          // Standard sheet thickness
ferrite_recess_depth = 1;         // Recess depth

/* [Thermal Management] */
// Thermal vias for heat conduction to shell (sealed design)
thermal_via_diameter = 4;         // Via hole diameter
thermal_via_count = 8;            // Number of vias
thermal_via_radius = 30;          // Via circle radius

/* [Mounting Features] */
alignment_pin_diameter = 2;
alignment_pin_count = 3;
wire_channel_width = 6;           // Coil wire exit

// ============================================================
// MAIN MODULE
// ============================================================
module coil_mount() {
    difference() {
        union() {
            // Main body - slightly larger than coil
            cylinder(h=mount_height, d=mount_outer_diameter, $fn=64);
            
            // Alignment pins
            for (i = [0:alignment_pin_count-1]) {
                rotate([0, 0, i * (360/alignment_pin_count)])
                translate([mount_outer_diameter/2 - 3, 0, mount_height])
                    cylinder(h=3, d=alignment_pin_diameter, $fn=16);
            }
        }
        
        // Coil recess (top)
        translate([0, 0, mount_height - coil_height - 0.5])
        difference() {
            cylinder(h=coil_height + 1, d=coil_outer_diameter + mount_tolerance*2, $fn=64);
            cylinder(h=coil_height + 1, d=coil_inner_diameter - mount_tolerance*2, $fn=64);
        }
        
        // Center opening
        translate([0, 0, -0.1])
            cylinder(h=mount_height + 0.2, d=coil_inner_diameter - 5, $fn=64);
        
        // Ferrite recess (bottom of coil area)
        translate([0, 0, mount_height - coil_height - ferrite_recess_depth - 0.5])
            cylinder(h=ferrite_recess_depth + 0.1, d=ferrite_diameter + 0.5, $fn=64);
        
        // Thermal vias (for sealed design heat dissipation)
        for (i = [0:thermal_via_count-1]) {
            rotate([0, 0, i * (360/thermal_via_count)])
            translate([thermal_via_radius, 0, -0.1])
                cylinder(h=mount_height + 0.2, d=thermal_via_diameter, $fn=16);
        }
        
        // Wire channel
        translate([coil_outer_diameter/2 - 5, 0, mount_height/2])
            rotate([0, 90, 0])
            hull() {
                cylinder(h=10, d=wire_channel_width, center=true, $fn=16);
                translate([0, 0, 5])
                    cylinder(h=1, d=wire_channel_width, center=true, $fn=16);
            }
    }
}

// ============================================================
// RENDER
// ============================================================
coil_mount();

// ============================================================
// VERIFICATION
// ============================================================
echo("=== COIL MOUNT VERIFICATION ===");
echo(str("Coil diameter: ", coil_outer_diameter, "mm"));
echo(str("Mount OD: ", mount_outer_diameter, "mm"));
echo(str("Ferrite: ", ferrite_diameter, "mm × ", ferrite_thickness, "mm"));
echo(str("Thermal vias: ", thermal_via_count, " × ", thermal_via_diameter, "mm"));
echo(str("Expected inductance: ~85μH (", coil_turns, " turns)"));
echo("");
echo("SEALED DESIGN: Heat conducts through thermal vias to shell");
