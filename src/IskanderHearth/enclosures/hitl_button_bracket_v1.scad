// =============================================================================
// ISKANDER HEARTH — HITL Button Bracket v1
// File: hitl_button_bracket_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
// Phase   : 6 — Glass Box Physical UX
//
// A front-panel mounting bracket for 2× Sanwa OBSA-30 arcade buttons.
// Slots into the existing front panel USB-A cutout (34mm wide × 16mm tall)
// from chassis v1, or the larger cutout defined in hearth_chassis_v2.scad.
//
// The bracket is printed in PETG and friction-fit into the front panel opening.
// Buttons push in from the outside and are retained by their M12/M16 nuts.
//
// BUTTONS: Sanwa OBSA-30, 30mm mounting hole, LED-illuminated, momentary NO+NC
//   Veto  = left position  (red cap)
//   Sign  = right position (green cap)
//
// PRINT SETTINGS: 3 perimeters, 30% gyroid infill, 0.2mm layer, PETG
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS
// =============================================================================

// --- Button dimensions ---
btn_mount_d    = 30.0;  // [mm] Sanwa OBSA-30 mounting hole diameter (press-fit nut spec)
btn_clear_d    = 31.5;  // [mm] Clearance hole (mounting hole + fit_tolerance)
btn_spacing    = 48.0;  // [mm] Centre-to-centre of the two buttons
                         //      Chosen to fit two 30mm buttons with 18mm between outer edges

// --- Bracket body ---
bracket_w      = 100;   // [mm] Bracket width (wider than button pair for mounting ears)
bracket_h      = 50;    // [mm] Bracket height (front face)
bracket_depth  = wall_t;// [mm] Bracket depth = panel thickness (flush with chassis wall)
wall_t         = 3.0;   // [mm] Wall thickness (matches chassis wall_thickness)

// --- Front panel slot (the opening this bracket sits in) ---
// In chassis_v2, the front panel has a cutout defined as:
//   bracket_slot_w × bracket_slot_h at the correct Z position
bracket_slot_w = bracket_w;
bracket_slot_h = bracket_h;

// --- LED wire channel ---
wire_channel_d = 5;     // [mm] Diameter of wire pass-through channels in bracket body

// --- Fit tolerance ---
fit_tolerance  = 0.4;   // [mm] Print fit clearance (increase to 0.6 if tight)


// =============================================================================
// SECTION 2 — BRACKET BODY
// =============================================================================

module hitl_button_bracket() {
    difference() {
        // Bracket body — fills the front panel slot
        cube([bracket_w, bracket_depth, bracket_h]);

        // Left button (Veto) — centred in left half
        translate([bracket_w / 2 - btn_spacing / 2, -0.1, bracket_h / 2])
        rotate([-90, 0, 0])
        cylinder(d = btn_clear_d + fit_tolerance, h = bracket_depth + 0.2, $fn = 64);

        // Right button (Sign) — centred in right half
        translate([bracket_w / 2 + btn_spacing / 2, -0.1, bracket_h / 2])
        rotate([-90, 0, 0])
        cylinder(d = btn_clear_d + fit_tolerance, h = bracket_depth + 0.2, $fn = 64);

        // Wire pass-through channels — bottom of bracket, one per button
        for (x_off = [bracket_w / 2 - btn_spacing / 2, bracket_w / 2 + btn_spacing / 2]) {
            translate([x_off, bracket_depth / 2, wall_t])
            cylinder(d = wire_channel_d, h = bracket_h / 2 - 5, $fn = 16);
        }

        // Single combined wire exit at bottom edge (routes to HAT)
        translate([bracket_w / 2 - wire_channel_d / 2, -0.1, wall_t / 2])
        cube([wire_channel_d * 2 + btn_spacing / 2, bracket_depth + 0.2, wall_t]);
    }

    // Mounting ears (extend left and right past the slot for screw retention)
    ear_w = 8;
    ear_h = 10;
    for (side = [0, bracket_w - ear_w]) {
        translate([side, 0, bracket_h / 2 - ear_h / 2])
        difference() {
            cube([ear_w, bracket_depth, ear_h]);
            // M3 retention screw hole in ear
            translate([ear_w / 2, -0.1, ear_h / 2])
            rotate([-90, 0, 0])
            cylinder(d = 3.2, h = bracket_depth + 0.2, $fn = 16);
        }
    }
}


// =============================================================================
// SECTION 3 — BUTTON LABEL (optional engraved text)
// Uncomment to add engraved labels.
// Requires a TTF font available to OpenSCAD.
// =============================================================================

// module button_labels() {
//     // "VETO" label under left button
//     translate([bracket_w/2 - btn_spacing/2 - 10, bracket_depth, bracket_h/2 - 22])
//     linear_extrude(height = 0.6)
//     text("VETO", size = 5, font = "Liberation Sans:style=Bold", halign = "center");
//
//     // "SIGN" label under right button
//     translate([bracket_w/2 + btn_spacing/2 - 8, bracket_depth, bracket_h/2 - 22])
//     linear_extrude(height = 0.6)
//     text("SIGN", size = 5, font = "Liberation Sans:style=Bold", halign = "center");
// }


// =============================================================================
// SECTION 4 — RENDER
// =============================================================================

hitl_button_bracket();

// button_labels();   // <-- uncomment to add engraved labels

// Preview ghost of installed buttons (30mm cylinders at correct positions):
// %translate([bracket_w/2 - btn_spacing/2, 30, bracket_h/2]) rotate([-90,0,0]) cylinder(d=30, h=50, $fn=64);
// %translate([bracket_w/2 + btn_spacing/2, 30, bracket_h/2]) rotate([-90,0,0]) cylinder(d=30, h=50, $fn=64);
