// =============================================================================
// ISKANDER HEARTH — Tier 2 Commons Node Chassis v2
// File: hearth_chassis_v2.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
// Phase   : 6 — Glass Box Physical UX | 7 — Thermal & Acoustic Validation
// Depends : hearth_chassis_v1.scad (helper modules via `use`)
//
// v2 CHANGES FROM v1:
//   front_panel() — adds 2× HITL button cutouts (Sanwa OBSA-30, 30mm)
//                   alongside existing 16mm power button.
//   top_panel()   — adds recessed NeoPixel LED channel with diffuser clip rails
//                   (holds led_matrix_mount_v1 insert).
//   rear_panel_v2() — [Phase 7] adds 4× duct clip receiver tabs around the
//                   120mm exhaust fan mount. fan_duct_v1.scad (exhaust variant)
//                   snap-clips into these tabs.
//
// Phase 7 fan notes:
//   Target fan: Noctua NF-A12x25 PWM (P7-001) — 120mm, 105mm screw spacing.
//   Existing fan_cutout() parameters already match. No aperture change required.
//   For Noctua NF-A14 (140mm, P7-002): place fan_140mm_adapter_v1 over the
//   top-panel 120mm cutout. Requires no chassis modification.
//
// ALL v1 parameters are reproduced here unchanged so this file is self-contained.
// A human engineer should keep this in sync with v1 if v1 parameters change.
//
// TO PRINT/CUT A SINGLE PANEL:
//   Comment out full_chassis_v2() at the bottom.
//   Uncomment the panel you want.
//   F6 → Export as STL.
// =============================================================================

// Import all helper modules from v1 (does NOT re-execute its render statement)
use <hearth_chassis_v1.scad>


// =============================================================================
// SECTION 1 — v1 PARAMETERS (reproduced — keep in sync with hearth_chassis_v1.scad)
// =============================================================================

wall_thickness      = 3;
mb_width            = 170;
mb_depth            = 170;
mb_pcb_t            = 1.6;
mb_standoff_h       = 6.5;
cpu_cooler_max_h    = 58;
gpu_length          = 240;
gpu_slot_width      = 40;
gpu_height          = 111;
gpu_clearance_mm    = 12;
psu_w               = 125;
psu_d               = 100;
psu_h               = 63.5;
ssd_w               = 70;
ssd_d               = 100;
ssd_h               = 9;
ssd_bay_count       = 2;
ssd_bay_gap         = 3;
fan_size            = 120;
fan_screw_spacing   = 105;
qr_size             = 30;
qr_recess_depth     = 0.8;
qr_border           = 2;
vent_slot_w         = 3;
vent_slot_gap       = 4;
vent_slot_len       = 60;
fit_tolerance       = 0.4;

// Derived (same as v1)
mb_zone_h           = mb_standoff_h + mb_pcb_t + cpu_cooler_max_h;
gpu_zone_h          = gpu_height + gpu_clearance_mm;
ssd_zone_h          = ssd_bay_count * ssd_h + (ssd_bay_count - 1) * ssd_bay_gap;
int_w               = mb_width + psu_w + wall_thickness * 3 + 20;
int_d               = gpu_length + 30;
int_h               = mb_zone_h + gpu_zone_h + ssd_zone_h + 40;
ext_w               = int_w + wall_thickness * 2;
ext_d               = int_d + wall_thickness * 2;
ext_h               = int_h + wall_thickness * 2;
mb_hole_inset       = 6.35;
mb_hole_pattern     = 154.94;
io_shield_w         = 158.76;
io_shield_h         = 44.45;
pcie_from_mb_top    = 149.86;
qr_platform         = qr_size + qr_border * 2;
qr_platform_h       = 2.5;


// =============================================================================
// SECTION 2 — Phase 6 PARAMETERS
// =============================================================================

// --- HITL Buttons (Sanwa OBSA-30) ---
btn_hole_d          = 30.0 + fit_tolerance;  // [mm] 30mm button + tolerance
btn_spacing         = 48.0;                  // [mm] Centre-to-centre of two buttons
// Button cluster centred horizontally, placed 30mm above the power button centre
btn_cluster_z       = ext_h * 0.75 + 30;    // [mm] Z height of button centres on front panel
btn_left_x          = ext_w / 2 - btn_spacing / 2;   // Veto (left / red)
btn_right_x         = ext_w / 2 + btn_spacing / 2;   // Sign (right / green)

// --- NeoPixel LED channel in top panel ---
neo_channel_w       = 14;   // [mm] Channel interior width (10mm strip + 2mm each side)
neo_channel_h       = 15;   // [mm] Channel depth (strip + diffuser gap + diffuser thickness)
neo_channel_wall    = 2.5;  // [mm] Channel wall thickness (3D-printed channel sits in this slot)
// Channel runs the full chassis depth minus margins, centred on chassis width
neo_channel_length  = ext_d - wall_thickness * 4;
neo_channel_x       = ext_w / 2 - (neo_channel_w + neo_channel_wall * 2) / 2;
neo_channel_y       = wall_thickness * 2;   // [mm] From rear of chassis

// Diffuser clip rail rebate (for led_matrix_mount insert)
// The chassis slot is slightly wider than the mount to allow clip-in
neo_slot_w          = neo_channel_w + neo_channel_wall * 2 + fit_tolerance;
neo_slot_h          = neo_channel_h + neo_channel_wall + fit_tolerance;


// =============================================================================
// SECTION 3 — OVERRIDDEN PANEL MODULES
// =============================================================================

// --- FRONT PANEL v2 ---
// Identical to v1 except: adds 2× 30mm HITL button holes and a combined
// annotation label slot above the button pair.
module front_panel_v2() {
    difference() {
        cube([ext_w, wall_thickness, ext_h]);

        // ── From v1 ──────────────────────────────────────────────────────────
        // 16mm power button (v1 position, unchanged)
        translate([ext_w / 2, -0.1, ext_h * 0.75])
        rotate([-90, 0, 0])
        cylinder(d = 16 + fit_tolerance, h = wall_thickness + 0.2, $fn = 32);

        // Lower intake ventilation (v1, unchanged)
        translate([wall_thickness * 3, -0.1, wall_thickness * 2])
        vent_grid(
            grid_w = ext_w - wall_thickness * 6,
            grid_h = ext_h * 0.30,
            depth  = wall_thickness + 0.2
        );

        // ── Phase 6 additions ────────────────────────────────────────────────
        // Veto button (left, red) — 30mm hole
        translate([btn_left_x, -0.1, btn_cluster_z])
        rotate([-90, 0, 0])
        cylinder(d = btn_hole_d, h = wall_thickness + 0.2, $fn = 64);

        // Sign button (right, green) — 30mm hole
        translate([btn_right_x, -0.1, btn_cluster_z])
        rotate([-90, 0, 0])
        cylinder(d = btn_hole_d, h = wall_thickness + 0.2, $fn = 64);

        // Wire pass-through slot between buttons (routes wiring to HAT)
        translate([
            ext_w / 2 - 6,
            -0.1,
            btn_cluster_z - btn_spacing / 2 - 10
        ])
        cube([12, wall_thickness + 0.2, 8]);
    }

    // Optional: embossed label platform between Veto and Sign
    // "VETO | SIGN" engraved text on exterior face
    // Uncomment when font is available:
    // translate([ext_w / 2 - 15, wall_thickness, btn_cluster_z - 18])
    // linear_extrude(height = 0.8)
    // text("VETO   SIGN", size = 4, font = "Liberation Sans:style=Bold", halign = "center");
}


// --- TOP PANEL v2 ---
// Identical to v1 except: adds a recessed channel slot for the LED matrix mount.
// The led_matrix_mount_v1 insert clips into this slot from above.
module top_panel_v2() {
    difference() {
        cube([ext_w, ext_d, wall_thickness]);

        // ── From v1 ──────────────────────────────────────────────────────────
        // 120mm intake fan (v1 position, unchanged)
        translate([ext_w / 2, ext_d * 0.33, -0.1])
        fan_cutout(size = fan_size, screw_spacing = fan_screw_spacing,
                   depth = wall_thickness + 0.2);

        // Supplementary passive ventilation (v1, unchanged)
        translate([wall_thickness * 2, ext_d * 0.50, -0.1])
        vent_grid(
            grid_w = ext_w - wall_thickness * 4,
            grid_h = ext_d * 0.38,
            depth  = wall_thickness + 0.2
        );

        // ── Phase 6 additions ────────────────────────────────────────────────
        // NeoPixel LED channel slot — routed into top panel
        // The led_matrix_mount_v1 insert press-fits into this opening.
        translate([neo_channel_x, neo_channel_y, wall_thickness - neo_slot_h + 0.1])
        cube([neo_slot_w, neo_channel_length, neo_slot_h + 0.1]);

        // Wire exit notch at rear end of channel (JST connector egress)
        translate([neo_channel_x + neo_slot_w / 2 - 5,
                   neo_channel_y + neo_channel_length - 1,
                   -0.1])
        cube([10, wall_thickness + 0.2, wall_thickness + 0.2]);
    }
}


// =============================================================================
// SECTION 4 — PHASE 7: REAR PANEL v2 (exhaust fan duct clip receivers)
// =============================================================================

// Duct clip receiver tab dimensions (matches snap_clip() in fan_duct_v1.scad)
duct_clip_tab_w     = 12;   // [mm] Receiver slot width (clip_w + 2mm clearance)
duct_clip_tab_h     = 8;    // [mm] Receiver slot height (clip_h + 3mm retention)
duct_clip_tab_t     = 3.5;  // [mm] Receiver wall thickness

// Exhaust fan centre position on rear panel (matches fan_cutout() in rear_panel())
// From rear_panel() in v1: fan centred at ext_w/2, height ext_h * 0.62
exhaust_fan_x       = ext_w / 2;
exhaust_fan_z       = ext_h * 0.62;
exhaust_fan_r       = (fan_size - 5) / 2;   // Inner radius of fan aperture

module duct_clip_receiver() {
    // A small L-bracket that protrudes inward from the rear panel face.
    // The fan_duct_v1.scad snap clip slides into the slot and hooks under the lip.
    // 4× instances placed at ±X and ±Z positions around the fan mount circle.
    union() {
        // Receiver body
        cube([duct_clip_tab_w, duct_clip_tab_t, duct_clip_tab_h]);
        // Retention lip (overhangs to capture the duct clip hook)
        translate([0, duct_clip_tab_t, duct_clip_tab_h - 2])
        cube([duct_clip_tab_w, 2.5, 2]);
    }
}

module rear_panel_v2() {
    // Rear panel with v1 geometry + Phase 7 duct clip receivers
    // The v1 rear_panel() module is called via `use` — we cannot directly call
    // it here and add to it, so we reproduce the additive elements only.
    // HUMAN NOTE: In KiCad/mechanical workflow, merge this with rear_panel() output.
    //
    // For standalone render: uncomment rear_panel() below and use union().

    // union() {
    //     rear_panel();  // from v1 via `use`

    // 4× duct clip receivers around the exhaust fan mount
    // Positioned just outside the fan aperture rim, at interior face (Y=0 in local coords)
    translate([0, ext_d - wall_thickness, 0]) {
        // +X clip receiver (right of fan)
        translate([exhaust_fan_x + exhaust_fan_r + 2, 0, exhaust_fan_z - duct_clip_tab_w/2])
        duct_clip_receiver();

        // -X clip receiver (left of fan)
        translate([exhaust_fan_x - exhaust_fan_r - 2 - duct_clip_tab_w, 0, exhaust_fan_z - duct_clip_tab_w/2])
        duct_clip_receiver();

        // +Z clip receiver (above fan)
        translate([exhaust_fan_x - duct_clip_tab_w/2, 0, exhaust_fan_z + exhaust_fan_r + 2])
        rotate([0, 0, 90])
        duct_clip_receiver();

        // -Z clip receiver (below fan)
        translate([exhaust_fan_x - duct_clip_tab_w/2, 0, exhaust_fan_z - exhaust_fan_r - 2 - duct_clip_tab_h])
        rotate([0, 0, 90])
        duct_clip_receiver();
    }
    // }  // end union
}


// =============================================================================
// SECTION 5 — FULL CHASSIS v2 ASSEMBLY
// Uses v2 overrides for front, top, and rear panels.
// =============================================================================

module full_chassis_v2() {
    // Bottom panel (v1, unchanged)
    bottom_panel();

    // TOP PANEL — v2 (NeoPixel channel slot)
    translate([0, 0, ext_h - wall_thickness])
    top_panel_v2();

    // FRONT PANEL — v2 (HITL button holes)
    front_panel_v2();

    // REAR PANEL — v2 adds duct clip receivers over v1 rear panel geometry
    // NOTE: rear_panel() from v1 must be unioned with duct clips in full build.
    // Run rear_panel_v2() for Phase 7 clip geometry; union with rear_panel() manually.
    translate([0, ext_d - wall_thickness, 0])
    rear_panel();          // v1 base geometry

    rear_panel_v2();       // Phase 7 clip receiver additions (additive, no subtraction)

    // Left side panel (v1, unchanged)
    left_panel();

    // Right side panel (v1, unchanged)
    translate([ext_w - wall_thickness, 0, 0])
    right_panel();

    // Motherboard tray (v1, unchanged)
    translate([
        ext_w - wall_thickness * 2 - (mb_width + 10),
        wall_thickness + (int_d - (mb_depth + 10)) / 2,
        ext_h - wall_thickness - mb_zone_h
    ])
    mb_tray();
}


// =============================================================================
// SECTION 6 — RENDER
// =============================================================================

full_chassis_v2();

// component_ghosts();    // <-- uncomment to check component clearances (from v1)

// Individual panel exports:
// bottom_panel();
// top_panel_v2();
// front_panel_v2();
// rear_panel();          // v1 base rear panel
// rear_panel_v2();       // Phase 7 duct clip receivers only (union with rear_panel for final STL)
// left_panel();
// right_panel();
// mb_tray();
