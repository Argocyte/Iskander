// =============================================================================
// ISKANDER HEARTH — Solidarity HAT Mounting Bracket v1
// File: sensor_hat_bracket.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
// Phase   : 6 — Glass Box Physical UX (referenced from Phase 5 assembly guide)
//
// PCB mounting bracket for the Solidarity HAT (65×56mm, 2-layer FR4).
// Mounts to the chassis interior right side panel using M3 screws.
// PCB retained by M3×5mm standoffs at four corners.
//
// HAT PCB MOUNTING HOLES: 4× M3, 2.5mm from each PCB edge corner.
//   Hole A: (2.5, 2.5)
//   Hole B: (62.5, 2.5)
//   Hole C: (2.5, 53.5)
//   Hole D: (62.5, 53.5)
//
// PRINT SETTINGS: 3 perimeters, 40% gyroid infill, 0.2mm layer, PETG
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS
// =============================================================================

// --- HAT PCB dimensions ---
hat_pcb_w    = 65.0;    // [mm] Solidarity HAT width
hat_pcb_d    = 56.0;    // [mm] Solidarity HAT depth
hat_pcb_t    = 1.6;     // [mm] PCB thickness (standard FR4)
hat_hole_d   = 3.2;     // [mm] M3 clearance hole diameter
hat_hole_inset = 2.5;   // [mm] Hole distance from PCB edge

// --- Standoff ---
standoff_h   = 8.0;     // [mm] PCB standoff height (clears J1 through-hole pins below)
standoff_od  = 5.0;     // [mm] Standoff outer diameter

// --- Bracket base plate ---
base_t       = 3.0;     // [mm] Base plate thickness
base_margin  = 5.0;     // [mm] Margin around PCB footprint
base_w       = hat_pcb_w + base_margin * 2;
base_d       = hat_pcb_d + base_margin * 2;

// --- Chassis mounting holes (for screwing bracket to side panel) ---
chassis_hole_d = 3.2;   // [mm] M3 clearance
chassis_hole_spacing_w = base_w - 8;  // [mm] Horizontal span
chassis_hole_spacing_d = base_d - 8;  // [mm] Vertical span

// --- Fit tolerance ---
fit_t        = 0.4;


// =============================================================================
// SECTION 2 — MODULE
// =============================================================================

module solidarity_hat_bracket() {
    // PCB mounting hole positions relative to bracket origin (at base_margin offset)
    holes = [
        [hat_hole_inset + base_margin, hat_hole_inset + base_margin],
        [hat_pcb_w - hat_hole_inset + base_margin, hat_hole_inset + base_margin],
        [hat_hole_inset + base_margin, hat_pcb_d - hat_hole_inset + base_margin],
        [hat_pcb_w - hat_hole_inset + base_margin, hat_pcb_d - hat_hole_inset + base_margin],
    ];

    difference() {
        // Base plate
        cube([base_w, base_d, base_t]);

        // Chassis mounting holes (corner positions)
        for (x_off = [4, base_w - 4]) {
            for (y_off = [4, base_d - 4]) {
                translate([x_off, y_off, -0.1])
                cylinder(d = chassis_hole_d, h = base_t + 0.2, $fn = 16);
            }
        }

        // Cable pass-through slot (for I2C/GPIO wiring to J1)
        // Centred in bracket, wide enough for 2×20 connector cable bundle
        translate([base_w / 2 - 15, base_d / 2 - 5, -0.1])
        cube([30, 10, base_t + 0.2]);
    }

    // PCB standoffs at each hole position
    for (pos = holes) {
        translate([pos[0], pos[1], base_t])
        difference() {
            cylinder(d = standoff_od, h = standoff_h, $fn = 16);
            // M3 thread hole (tap M3 after printing, or use heat-set M3 insert)
            translate([0, 0, -0.1])
            cylinder(d = 2.5, h = standoff_h + 0.2, $fn = 16);  // 2.5mm = M3 tap drill
        }
    }
}


// =============================================================================
// SECTION 3 — RENDER
// =============================================================================

solidarity_hat_bracket();

// HAT ghost (for clearance check):
// %translate([base_margin, base_margin, base_t + standoff_h])
//   cube([hat_pcb_w, hat_pcb_d, hat_pcb_t]);
