// =============================================================================
// ISKANDER HEARTH — NeoPixel LED Matrix Top Panel Mount v1
// File: led_matrix_mount_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
// Phase   : 6 — Glass Box Physical UX
//
// A recessed channel that sits in the top panel of the chassis and holds the
// WS2812B NeoPixel strip (P6-002: 60 LED/m, 0.5m, 30 LEDs total) behind a
// 3mm frosted acrylic diffuser panel (P6-003).
//
// MOUNTING: The mount clips into a routed slot in the chassis v2 top panel.
//           Diffuser panel slides in from the side and is retained by clip rails.
//
// DIMENSIONS:
//   Strip width: 10mm (WS2812B 60/m PCB width)
//   Strip length: 500mm (0.5m, 30 LEDs)
//   Diffuser: 3mm frosted acrylic, cut to channel opening dimensions
//
// PRINT SETTINGS: 4 perimeters, 20% gyroid infill, 0.2mm layer, white PETG
//                 (white interior reflects light from strip toward diffuser)
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS
// =============================================================================

// --- LED strip dimensions ---
strip_l     = 500;  // [mm] Strip length (0.5m)
strip_w     = 10;   // [mm] Strip PCB width (WS2812B 60/m)
strip_h     = 3;    // [mm] Strip PCB + LED height above adhesive back

// --- Channel body ---
channel_w   = strip_w + 4;   // [mm] Channel interior width (strip + 2mm each side)
channel_h   = strip_h + 10;  // [mm] Channel depth (strip + diffuser gap + diffuser)
channel_t   = 2.5;            // [mm] Channel wall thickness

// --- Diffuser ---
diffuser_t  = 3;    // [mm] 3mm frosted acrylic
diffuser_gap = 7;   // [mm] Air gap between strip LEDs and diffuser (softens dot pattern)

// --- Clip rail (retains diffuser) ---
clip_t      = 1.5;  // [mm] Clip rail thickness
clip_inset  = 1.0;  // [mm] How far the clip overhangs to retain diffuser

// --- Mounting tabs ---
tab_w       = 8;    // [mm] Width of chassis mounting tabs
tab_h       = 6;    // [mm] Height of mounting tabs
tab_slot_w  = strip_l;  // Tabs spaced at strip length

// --- Fit tolerance ---
fit_t       = 0.3;  // [mm] Tight press-fit for diffuser rail


// =============================================================================
// SECTION 2 — MODULES
// =============================================================================

// Cross-section profile of the LED channel (extruded along strip length)
module channel_profile() {
    outer_w = channel_w + channel_t * 2;
    outer_h = channel_h + channel_t;

    difference() {
        // Outer body
        square([outer_w, outer_h]);

        // Inner channel (open at top for diffuser)
        translate([channel_t, channel_t])
        square([channel_w, channel_h]);
    }

    // Diffuser clip rails — top inner corners, inset to retain 3mm diffuser
    translate([channel_t, channel_t + diffuser_gap + strip_h - clip_t])
    square([clip_inset + fit_t, clip_t]);

    translate([channel_t + channel_w - clip_inset - fit_t, channel_t + diffuser_gap + strip_h - clip_t])
    square([clip_inset + fit_t, clip_t]);
}


module led_channel_mount() {
    // Main channel body — linear extrusion of cross-section along strip length
    linear_extrude(height = strip_l)
    channel_profile();

    // Mounting tabs at each end (for chassis top panel retention)
    for (z_pos = [0, strip_l - tab_w]) {
        translate([0, channel_h + channel_t, z_pos])
        cube([channel_w + channel_t * 2, tab_h, tab_w]);
    }
}


// Diffuser blank (for reference / manual cutting guide output)
// Use projection(cut=true) to get DXF profile for laser cutting
module diffuser_blank() {
    cube([channel_w + fit_t * 2, diffuser_t, strip_l]);
}


// Wire exit port at one end of the channel (for JST-XH connector clearance)
module wire_exit() {
    translate([channel_t + channel_w / 2 - 5, -0.1, 0])
    cube([10, channel_t + 0.2, 15]);
}


// =============================================================================
// SECTION 3 — RENDER
// =============================================================================

difference() {
    led_channel_mount();
    wire_exit();
}

// diffuser_blank();   // <-- uncomment to export diffuser DXF outline via projection

// Strip ghost (for clearance check):
// %translate([channel_t + 2, channel_t, 0]) cube([strip_w, strip_h, strip_l]);
