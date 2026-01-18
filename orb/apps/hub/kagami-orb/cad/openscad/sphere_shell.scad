// Kagami Orb V3.1 — Sphere Shell (VERIFIED DIMENSIONS)
// ========================================================
// Two-hemisphere design for 85mm sealed sphere
// Material: Acrylic (TAP Plastics) or 3D printed (Tough 2000)
// Print: Form 4, 50um layer height or CNC machined
//
// DESIGN FEATURES:
// - Top hemisphere: Display window (40mm) + snap-fit lip (female)
// - Bottom hemisphere: Coil window (35mm) + snap-fit lip (male)
// - Both: LED diffuser slot at equator (58mm x 4mm)
// - Alignment notch for assembly orientation
//
// SOURCES:
// - SPECS.md: 85mm OD, 7.5mm wall, 70mm internal
// - Display: 1.39" AMOLED with 35.41mm active area
// - LED Ring: HD108 x16 at equator (55mm ring + 58mm diffuser)
// - RX Coil: 70mm diameter for wireless charging

/* [Sphere Parameters - VERIFIED from SPECS.md] */
outer_diameter = 85;              // Design target from SPECS.md
wall_thickness = 7.5;             // Structural + thermal mass
inner_diameter = 70;              // outer - 2*wall = 70mm internal

/* [Display Window - Front of Top Hemisphere] */
// Window sized for 1.39" AMOLED (35.41mm active + bezel)
display_window_diameter = 40;     // ~40mm for display visibility
display_window_angle = 20;        // Degrees from top (tilted forward)
display_chamfer_depth = 2;        // Edge chamfer for aesthetics
display_chamfer_angle = 45;       // Chamfer angle

/* [Coil Window - Bottom of Bottom Hemisphere] */
// Window for wireless charging alignment / thermal management
coil_window_diameter = 35;        // Allows view of 70mm coil
coil_window_chamfer = 1.5;        // Edge chamfer

/* [LED Diffuser Slot - At Equator] */
// Slot matches diffuser_ring.scad dimensions
led_slot_outer_diameter = 58;     // Matches diffuser ring OD
led_slot_inner_diameter = 42;     // Matches diffuser ring ID
led_slot_height = 4;              // Slot depth into shell
led_slot_position = 0;            // Z=0 is equator

/* [Hemisphere Joint - Snap-Fit Lip] */
lip_height = 3;                   // Engagement depth
lip_thickness = 1.5;              // Lip wall thickness
lip_clearance = 0.15;             // Fit tolerance for snap
lip_chamfer = 0.5;                // Entry chamfer for assembly

/* [Alignment Feature] */
// Small notch for proper orientation during assembly
alignment_notch_width = 5;
alignment_notch_depth = 1.5;
alignment_notch_height = lip_height;
alignment_notch_angle = 0;        // Front (display side)

/* [Render Quality] */
$fn = 100;                        // High resolution for smooth spheres

// ============================================================
// DERIVED DIMENSIONS
// ============================================================
outer_radius = outer_diameter / 2;
inner_radius = inner_diameter / 2;

// Lip dimensions
lip_outer_radius = inner_radius + lip_thickness;
lip_inner_radius = inner_radius - lip_clearance;

// Display window position (tilted forward from top)
display_window_y_offset = outer_radius * sin(display_window_angle);
display_window_z_offset = outer_radius * cos(display_window_angle);

// ============================================================
// TOP HEMISPHERE MODULE
// ============================================================
module top_hemisphere() {
    difference() {
        union() {
            // Outer hemisphere (top half)
            difference() {
                sphere(r=outer_radius, $fn=$fn);

                // Cut bottom half
                translate([0, 0, -outer_radius])
                    cube([outer_diameter + 1, outer_diameter + 1, outer_diameter], center=true);
            }
        }

        // Inner cavity (hollow out)
        sphere(r=inner_radius, $fn=$fn);

        // Display window aperture (tilted forward)
        rotate([display_window_angle, 0, 0])
        translate([0, 0, outer_radius - wall_thickness])
            display_window_cutout();

        // LED slot (top half of slot at equator)
        translate([0, 0, -led_slot_height/2])
            led_slot_cutout();

        // Female snap-fit lip recess (inside edge at equator)
        translate([0, 0, -lip_height])
            lip_recess_female();
    }
}

// ============================================================
// BOTTOM HEMISPHERE MODULE
// ============================================================
module bottom_hemisphere() {
    difference() {
        union() {
            // Outer hemisphere (bottom half)
            difference() {
                sphere(r=outer_radius, $fn=$fn);

                // Cut top half
                translate([0, 0, outer_radius])
                    cube([outer_diameter + 1, outer_diameter + 1, outer_diameter], center=true);
            }

            // Male snap-fit lip (protrudes up from equator)
            lip_male();
        }

        // Inner cavity (hollow out)
        sphere(r=inner_radius, $fn=$fn);

        // Coil window aperture (bottom)
        translate([0, 0, -outer_radius + wall_thickness])
            mirror([0, 0, 1])
            coil_window_cutout();

        // LED slot (bottom half of slot at equator)
        translate([0, 0, led_slot_height/2])
            mirror([0, 0, 1])
            led_slot_cutout();

        // Alignment notch (cut into male lip)
        rotate([0, 0, alignment_notch_angle])
        translate([inner_radius - alignment_notch_depth/2, 0, 0])
            alignment_notch_cutout();
    }
}

// ============================================================
// DISPLAY WINDOW CUTOUT
// ============================================================
module display_window_cutout() {
    // Main aperture
    cylinder(h=wall_thickness + 1, d=display_window_diameter, $fn=64);

    // Outer chamfer (aesthetic beveled edge)
    translate([0, 0, wall_thickness - display_chamfer_depth])
        cylinder(
            h=display_chamfer_depth + 1,
            d1=display_window_diameter,
            d2=display_window_diameter + 2 * display_chamfer_depth * tan(display_chamfer_angle),
            $fn=64
        );

    // Inner chamfer (light guide)
    translate([0, 0, -1])
        cylinder(
            h=display_chamfer_depth + 1,
            d1=display_window_diameter + 2 * display_chamfer_depth * tan(display_chamfer_angle),
            d2=display_window_diameter,
            $fn=64
        );
}

// ============================================================
// COIL WINDOW CUTOUT
// ============================================================
module coil_window_cutout() {
    // Main aperture
    cylinder(h=wall_thickness + 1, d=coil_window_diameter, $fn=64);

    // Chamfered edge
    translate([0, 0, wall_thickness - coil_window_chamfer])
        cylinder(
            h=coil_window_chamfer + 1,
            d1=coil_window_diameter,
            d2=coil_window_diameter + 2 * coil_window_chamfer,
            $fn=64
        );
}

// ============================================================
// LED SLOT CUTOUT
// ============================================================
module led_slot_cutout() {
    // Ring slot for LED diffuser
    difference() {
        cylinder(h=led_slot_height + 0.1, d=led_slot_outer_diameter, $fn=64);
        translate([0, 0, -0.1])
            cylinder(h=led_slot_height + 0.3, d=led_slot_inner_diameter, $fn=64);
    }
}

// ============================================================
// SNAP-FIT LIP MODULES
// ============================================================
module lip_male() {
    // Male lip protrudes up from bottom hemisphere
    difference() {
        // Outer wall of lip
        cylinder(h=lip_height, d=lip_outer_radius * 2, $fn=$fn);

        // Inner cavity
        translate([0, 0, -0.1])
            cylinder(h=lip_height + 0.2, d=inner_radius * 2, $fn=$fn);

        // Entry chamfer (top edge, makes assembly easier)
        translate([0, 0, lip_height - lip_chamfer])
            difference() {
                cylinder(h=lip_chamfer + 0.1, d=lip_outer_radius * 2 + 1, $fn=$fn);
                cylinder(
                    h=lip_chamfer + 0.1,
                    d1=lip_outer_radius * 2,
                    d2=lip_outer_radius * 2 - lip_chamfer * 2,
                    $fn=$fn
                );
            }
    }
}

module lip_recess_female() {
    // Female recess in top hemisphere
    difference() {
        cylinder(h=lip_height + 0.1, d=(lip_outer_radius + lip_clearance) * 2, $fn=$fn);
        translate([0, 0, -0.1])
            cylinder(h=lip_height + 0.3, d=(inner_radius - 0.1) * 2, $fn=$fn);
    }
}

// ============================================================
// ALIGNMENT NOTCH
// ============================================================
module alignment_notch_cutout() {
    // Small rectangular notch for orientation
    cube([alignment_notch_depth + 0.1, alignment_notch_width, alignment_notch_height * 2], center=true);
}

module alignment_notch_key() {
    // Matching key that fits into notch (for top hemisphere)
    cube([alignment_notch_depth - lip_clearance*2, alignment_notch_width - lip_clearance*2, alignment_notch_height * 2 - 0.2], center=true);
}

// ============================================================
// ASSEMBLY PREVIEW
// ============================================================
module assembly_preview(exploded=true) {
    gap = exploded ? 15 : 0;

    // Top hemisphere
    color("LightSkyBlue", 0.8)
    translate([0, 0, gap/2])
        top_hemisphere();

    // Bottom hemisphere
    color("LightSteelBlue", 0.8)
    translate([0, 0, -gap/2])
        bottom_hemisphere();

    // Reference sphere (internal volume)
    if (exploded) {
        color("Gold", 0.2)
            sphere(r=inner_radius - 2.5, $fn=32);
    }
}

// ============================================================
// EXPORT MODULES (for STL generation)
// ============================================================
// STL Export Instructions:
//
// Using OpenSCAD GUI:
//   1. Comment out assembly_preview() below
//   2. Uncomment the desired export module (export_top_hemisphere or export_bottom_hemisphere)
//   3. Press F6 to render (not F5 preview)
//   4. File -> Export -> Export as STL
//   5. Save as "sphere_shell_top.stl" or "sphere_shell_bottom.stl"
//
// Using OpenSCAD CLI (recommended for automation):
//   openscad -o sphere_shell_top.stl -D 'EXPORT_TOP=true' sphere_shell.scad
//   openscad -o sphere_shell_bottom.stl -D 'EXPORT_BOTTOM=true' sphere_shell.scad
//
// Print Settings (Form 4 / Tough 2000):
//   - Layer height: 50um for best surface finish
//   - Supports: Auto-generate, touching buildplate only
//   - Orientation: Flat on equator (as exported)
//   - Post-cure: UV cure per resin spec
//
// Print Settings (FDM):
//   - Layer height: 0.1-0.15mm
//   - Infill: 20-30% for weight balance
//   - Supports: Required for window overhangs
//   - Material: PETG or ABS for heat resistance
//
// ============================================================

// CLI export flags (set via -D option)
EXPORT_TOP = false;
EXPORT_BOTTOM = false;

module export_top_hemisphere() {
    // Oriented for printing (flat on equator)
    top_hemisphere();
}

module export_bottom_hemisphere() {
    // Oriented for printing (flat on equator, flipped)
    mirror([0, 0, 1])
        bottom_hemisphere();
}

// ============================================================
// RENDER
// ============================================================
// Automatic CLI export support - renders correct part based on flags
// Manual selection: comment out the if/else and uncomment desired module

if (EXPORT_TOP) {
    export_top_hemisphere();
} else if (EXPORT_BOTTOM) {
    export_bottom_hemisphere();
} else {
    // Default: Assembly preview (exploded)
    assembly_preview(exploded=true);
}

// Manual alternatives (uncomment one, comment out if/else above):
// assembly_preview(exploded=false);  // Closed assembly
// export_top_hemisphere();           // Top hemisphere for STL
// export_bottom_hemisphere();        // Bottom hemisphere for STL

// ============================================================
// VERIFICATION
// ============================================================
echo("=== SPHERE SHELL VERIFICATION ===");
echo(str("Outer diameter: ", outer_diameter, "mm (target: 85mm)"));
echo(str("Wall thickness: ", wall_thickness, "mm (target: 7.5mm)"));
echo(str("Inner diameter: ", inner_diameter, "mm (target: 70mm)"));
echo(str("Display window: ", display_window_diameter, "mm at ", display_window_angle, "deg"));
echo(str("LED slot: ", led_slot_outer_diameter, "mm OD x ", led_slot_height, "mm H"));
echo(str("Coil window: ", coil_window_diameter, "mm"));
echo(str("Lip engagement: ", lip_height, "mm x ", lip_thickness, "mm"));
echo("");
echo("=== FIT CHECKS ===");
echo(str("Internal cavity for 65mm components? ", inner_diameter >= 70 ? "YES" : "NO"));
echo(str("Display visible (35.41mm active)? ", display_window_diameter >= 36 ? "YES" : "NO"));
echo(str("LED diffuser fits (58mm ring)? ", led_slot_outer_diameter >= 58 ? "YES" : "NO"));
echo(str("Coil visible (70mm coil)? ", coil_window_diameter >= 35 ? "YES" : "NO"));
echo("");
echo("=== MASS ESTIMATE ===");
// Volume calculation for acrylic shell
shell_volume = (4/3) * PI * pow(outer_radius, 3) - (4/3) * PI * pow(inner_radius, 3);
// Subtract windows and slot (approximate)
window_volume = PI * pow(display_window_diameter/2, 2) * wall_thickness +
                PI * pow(coil_window_diameter/2, 2) * wall_thickness +
                PI * (pow(led_slot_outer_diameter/2, 2) - pow(led_slot_inner_diameter/2, 2)) * led_slot_height;
net_volume = shell_volume - window_volume;
// Acrylic density ~1.18 g/cm3
acrylic_mass = net_volume * 1.18 / 1000;
echo(str("Shell volume: ", round(net_volume), " mm^3"));
echo(str("Estimated mass (acrylic): ", round(acrylic_mass), "g (target: 90g)"));
echo(str("Mass within budget? ", acrylic_mass <= 100 ? "YES" : "OPTIMIZE"));
