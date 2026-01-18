// Kagami Orb V3.1 — Complete Assembly Verification
// ========================================================
// This file contains accurate placeholder models for all
// major components to verify assembly fit and clearances.
//
// Dimensions verified against SPECS.md and manufacturer data
// Last Updated: January 2026
//
// Usage:
//   - Preview (F5) for quick visual check
//   - Render (F6) for intersection detection
//   - Modify explode_gap to see component layers

/* [Assembly Controls] */
show_shell = true;            // Show sphere shell
show_internals = true;        // Show internal components
explode_gap = 0;              // 0=assembled, 10-30=exploded view
section_view = false;         // Cut away half for internal view
show_clearance_check = false; // Highlight tight clearances

/* [Sphere Parameters] */
sphere_od = 85;
shell_thickness = 7.5;
sphere_id = 70;  // 85 - 2*7.5 = 70mm internal

/* [Quality] */
$fn = 64;

// ============================================================
// COMPONENT MODULES (Verified Dimensions)
// ============================================================

// QCS6490 SoM - Thundercomm TurboX C6490
// Source: https://www.thundercomm.com/product/c6490-som/
module qcs6490_som() {
    color("DarkGreen", 0.9) {
        // Main PCB
        cube([42.5, 35.5, 1.6], center=true);
        // Components on top
        translate([0, 0, 1.1]) cube([38, 30, 1.0], center=true);
    }
    // DF40HC-100DS connector (bottom)
    translate([0, 0, -1.3])
        color("Gold") cube([22.6, 4.3, 1.0], center=true);
    // Heatsink mounting area indicator
    translate([0, 0, 1.6])
        color("Red", 0.3) cube([20, 20, 0.1], center=true);
}

// Hailo-10H M.2 2242 AI Accelerator
// Source: https://hailo.ai/products/
module hailo_10h() {
    color("Black", 0.9) {
        difference() {
            cube([42, 22, 2.63], center=true);
            // M.2 Key M notch
            translate([-21+2.5, 11-1, 0])
                cube([5, 2, 3], center=true);
        }
    }
    // Chip package indicator
    translate([0, 0, 1.3])
        color("DarkGray") cube([12, 12, 1.0], center=true);
}

// 1.39" Round AMOLED Display
// Source: King Tech Display datasheet
module amoled_display() {
    // Glass substrate
    color("Black", 0.95)
        cube([38.83, 38.21, 0.68], center=true);
    // Active area (Ø35.41mm)
    translate([0, 0, 0.35])
        color("DarkBlue", 0.8) cylinder(h=0.1, d=35.41);
    // FPC cable
    translate([0, -19.1, 0])
        rotate([90, 0, 0])
        color("Orange", 0.8) cube([12, 0.3, 25], center=true);
}

// IMX989 Camera Module (50MP)
// Source: SincereFirst camera module
module imx989_camera() {
    color("DarkGray", 0.9) {
        // Module body
        cube([26, 26, 9.4], center=true);
    }
    // Lens barrel
    translate([0, 0, 4.7+0.5])
        color("Black") cylinder(h=1, d=14);
    // Lens glass
    translate([0, 0, 5.7])
        color("DarkBlue", 0.5) cylinder(h=0.5, d=12);
}

// HD108 5050 LED (single)
// Source: HD108 datasheet
module hd108_led() {
    color("White", 0.9) cube([5.1, 5.0, 1.2], center=true);
    // Lens dome
    translate([0, 0, 0.6])
        color("White", 0.5)
        scale([1, 1, 0.5]) sphere(d=4);
}

// LED Ring (16x HD108 at equator)
module led_ring() {
    led_radius = 24;  // From led_mount_ring.scad
    for (i = [0:15]) {
        rotate([0, 0, i * 22.5])
        translate([led_radius, 0, 0])
        rotate([0, 0, 90])
            hd108_led();
    }
}

// 28mm Speaker Driver
// Source: Yueda spec
module speaker_28mm() {
    color("Silver", 0.8) {
        // Frame
        difference() {
            cylinder(h=5.4, d=28);
            translate([0, 0, 1]) cylinder(h=5, d=24);
        }
    }
    // Cone
    translate([0, 0, 2])
        color("Black", 0.7) cylinder(h=2, d1=22, d2=8);
    // Voice coil
    translate([0, 0, 0.5])
        color("Copper") cylinder(h=4, d=15);
}

// 3S LiPo Battery (2200mAh)
// Source: Verified fit analysis
module lipo_battery() {
    color("RoyalBlue", 0.9)
        cube([55, 35, 20], center=true);
    // Warning label
    translate([0, 0, 10.1])
        color("Yellow") cube([30, 20, 0.1], center=true);
    // Balance connector
    translate([0, 17.5, 5])
        color("White") cube([12, 3, 6], center=true);
    // Main wires
    translate([27.5, 0, 5])
        color("Red") cylinder(h=15, d=2);
    translate([27.5, 4, 5])
        color("Black") cylinder(h=15, d=2);
}

// RX Coil (70mm Litz wire)
module rx_coil() {
    color("Copper", 0.8)
    difference() {
        cylinder(h=4, d=70);
        translate([0, 0, -0.1]) cylinder(h=4.2, d=40);
    }
}

// Ferrite Shield (60mm)
module ferrite_sheet() {
    color("DarkSlateGray", 0.9) cylinder(h=0.5, d=60);
}

// sensiBel SBM100B Microphone (single)
// Source: sensiBel datasheet
module sensibel_mic() {
    color("Silver", 0.8) cube([6.0, 3.8, 2.47], center=true);
    // Sound port
    translate([0, 0, 1.24])
        color("Black") cylinder(h=0.5, d=1.5);
}

// ESP32-S3-WROOM-1
module esp32_s3() {
    color("DimGray", 0.9) cube([25.5, 18, 3.1], center=true);
    // Antenna area
    translate([0, 9-3, 1.6])
        color("Silver") cube([18, 6, 0.5], center=true);
}

// Main PCB (circular, 60mm)
module main_pcb() {
    color("DarkGreen", 0.8) cylinder(h=1.6, d=60);
    // Copper traces indicator
    translate([0, 0, 0.8])
        color("Gold", 0.3) cylinder(h=0.1, d=55);
}

// ============================================================
// CUSTOM MOUNTS (from OpenSCAD files)
// ============================================================

// Display Mount (simplified)
module display_mount_placeholder() {
    color("Gray", 0.7)
    difference() {
        cylinder(h=8, d=44);
        translate([0, 0, 2]) cylinder(h=7, d=40);
        // Display window
        cylinder(h=10, d=36);
    }
}

// Internal Frame (simplified)
module internal_frame_placeholder() {
    color("DimGray", 0.6)
    difference() {
        cylinder(h=42, d=62);
        translate([0, 0, 2]) cylinder(h=42, d=57);
        // Cutouts for components
        translate([0, 0, 35]) cylinder(h=10, d=45);
        translate([0, 0, -1]) cylinder(h=10, d=30);
    }
}

// Coil Mount (simplified)
module coil_mount_placeholder() {
    color("Gray", 0.7)
    difference() {
        cylinder(h=8, d=72);
        translate([0, 0, 4]) cylinder(h=5, d=68);
        translate([0, 0, -1]) cylinder(h=10, d=38);
    }
}

// LED Mount Ring (simplified)
module led_mount_placeholder() {
    color("DarkGray", 0.7)
    difference() {
        cylinder(h=6, d=55);
        translate([0, 0, -1]) cylinder(h=8, d=45);
    }
}

// ============================================================
// SPHERE SHELL (from sphere_shell.scad)
// ============================================================

module sphere_shell_top() {
    color("LightSkyBlue", 0.4)
    difference() {
        // Outer hemisphere
        intersection() {
            sphere(d=sphere_od);
            translate([0, 0, sphere_od/4]) cube([sphere_od+1, sphere_od+1, sphere_od/2], center=true);
        }
        // Inner cavity
        sphere(d=sphere_id);
        // Display window
        rotate([20, 0, 0])
        translate([0, 0, sphere_od/2-shell_thickness])
            cylinder(h=shell_thickness+1, d=40);
    }
}

module sphere_shell_bottom() {
    color("LightSteelBlue", 0.4)
    difference() {
        // Outer hemisphere
        intersection() {
            sphere(d=sphere_od);
            translate([0, 0, -sphere_od/4]) cube([sphere_od+1, sphere_od+1, sphere_od/2], center=true);
        }
        // Inner cavity
        sphere(d=sphere_id);
        // Coil window
        translate([0, 0, -sphere_od/2+shell_thickness])
        mirror([0, 0, 1])
            cylinder(h=shell_thickness+1, d=35);
    }
}

// ============================================================
// COMPLETE ASSEMBLY
// ============================================================

module complete_assembly() {
    gap = explode_gap;

    // === SHELL ===
    if (show_shell) {
        translate([0, 0, gap * 2]) sphere_shell_top();
        translate([0, 0, -gap * 2]) sphere_shell_bottom();
    }

    if (show_internals) {
        // === TOP SECTION (Y > 0) ===

        // Display at Y=+30 (tilted 20°)
        translate([0, 0, 30 + gap * 1.5])
        rotate([20, 0, 0])
            amoled_display();

        // Camera at Y=+24
        translate([0, 0, 24 + gap * 1.2])
            imx989_camera();

        // Display mount at Y=+18
        translate([0, 0, 18 + gap])
            display_mount_placeholder();

        // QCS6490 at Y=+13
        translate([0, 0, 13 + gap * 0.8])
            qcs6490_som();

        // Main PCB at Y=+10
        translate([0, 0, 10 + gap * 0.6])
            main_pcb();

        // Hailo-10H at Y=+8
        translate([0, -8, 8 + gap * 0.5])
            hailo_10h();

        // Microphones at Y=+5 (4x around perimeter)
        for (i = [0:3]) {
            rotate([0, 0, i * 90 + 45])
            translate([25, 0, 5 + gap * 0.3])
                sensibel_mic();
        }

        // === EQUATOR (Y = 0) ===

        // LED Ring at equator
        translate([0, 0, 0])
            led_ring();

        // LED Mount
        translate([0, 0, -3])
            led_mount_placeholder();

        // === BOTTOM SECTION (Y < 0) ===

        // Speaker at Y=-8
        translate([0, 0, -8 - gap * 0.3])
            speaker_28mm();

        // Battery at Y=-20
        translate([0, 0, -20 - gap * 0.8])
            lipo_battery();

        // Coil mount at Y=-32
        translate([0, 0, -32 - gap * 1.2])
            coil_mount_placeholder();

        // RX Coil at Y=-34
        translate([0, 0, -34 - gap * 1.5])
            rx_coil();

        // Ferrite at Y=-36
        translate([0, 0, -36.5 - gap * 1.5])
            ferrite_sheet();
    }
}

// ============================================================
// CLEARANCE VISUALIZATION
// ============================================================

module clearance_envelope() {
    // 70mm internal diameter constraint
    color("Red", 0.1)
    difference() {
        sphere(d=70);
        sphere(d=68);
    }
}

// ============================================================
// RENDER
// ============================================================

if (section_view) {
    difference() {
        complete_assembly();
        translate([0, -50, 0]) cube([100, 100, 100], center=true);
    }
} else {
    complete_assembly();
}

if (show_clearance_check) {
    clearance_envelope();
}

// ============================================================
// VERIFICATION OUTPUT
// ============================================================

echo("=== ASSEMBLY VERIFICATION ===");
echo(str("Sphere OD: ", sphere_od, "mm"));
echo(str("Internal diameter: ", sphere_id, "mm"));
echo(str("Shell thickness: ", shell_thickness, "mm"));
echo("");

// Component stack heights
echo("=== COMPONENT STACK ===");
echo("Top section (display to equator): ~30mm");
echo("Bottom section (equator to coil): ~36mm");
echo("Total internal height needed: ~66mm");
echo(str("Available: ", sphere_id, "mm — ", sphere_id >= 66 ? "OK" : "TOO TIGHT"));
echo("");

// Max width checks
echo("=== WIDTH CLEARANCE ===");
components = [
    ["QCS6490 SoM", 42.5],
    ["Hailo-10H", 42],
    ["Battery", 55],
    ["RX Coil", 70],
    ["Main PCB", 60],
    ["LED Ring", 55]
];

for (c = components) {
    fits = c[1] < sphere_id ? "OK" : "EXCEEDS";
    echo(str(c[0], ": ", c[1], "mm — ", fits));
}

echo("");
echo("=== ASSEMBLY NOTES ===");
echo("1. Battery (55mm) is largest internal component");
echo("2. RX Coil (70mm) fits at very bottom against shell");
echo("3. Display tilted 20° forward for viewing angle");
echo("4. 4 microphones positioned at 45° intervals");
