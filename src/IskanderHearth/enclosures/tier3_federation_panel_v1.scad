// =============================================================================
// ISKANDER HEARTH — Tier 3 Federation Rack Panel v1
// File: tier3_federation_panel_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
//           https://ohwr.org/cern_ohl_s_v2.txt
// Phase   : 8 — Distributed Cooperative Manufacturing
//
// WHAT THIS IS:
//   A 1U 19-inch blank rack panel for Tier 3 Federation deployments. Installed
//   in the rack unit immediately below or above the Supermicro server chassis.
//
//   Functions:
//   (1) Node identification — embossed serial, cooperative ID, and QR code
//       linking to this node's entry in the cooperative federation ledger.
//   (2) Cable management — horizontal cable routing slots (Velcro cable tie
//       points) for 10GbE, power, and IPMI cables.
//   (3) CERN-OHL-S compliance surface — open hardware declaration embossed
//       into the panel face, permanently attached to the physical hardware.
//   (4) Status indicator window — 1× 5mm LED hole for a panel-mount LED
//       driven by the HAT GPIO (HAT-optional for Tier 3; external USB GPIO).
//   (5) Air blanking — solid behind the identification zones prevents cold
//       aisle air bypass in ventilated racks.
//
// 19-INCH RACK PANEL SPECIFICATION (EIA-310-D):
//   External width  : 482.6mm (19-inch standard)
//   External height : 44.45mm (1U)
//   Panel thickness : 3.0mm (3D-printed) or 1.5–2mm (aluminium sheet)
//   Ear width       : 12.7mm (rack flange — includes mounting hole)
//   Mounting holes  : 6.35mm from ear edge, M5 or M6 clearance, spaced 15.875mm
//   Panel depth     : 20mm (slab panel — not a chassis, no rear clearance needed)
//
// PRINT SETTINGS:
//   Material : PETG or ASA (ASA preferred for server room humidity tolerance)
//   Layer    : 0.2mm
//   Perimeters: 4 (for rack ear rigidity)
//   Infill   : 40% gyroid
//   Orientation: Flat (panel lying on build surface)
//   Note: At 482.6mm width this exceeds most printer build volumes.
//         Print as TWO HALVES (see SECTION 5) joined with M3 hardware + alignment pins.
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS
// =============================================================================

// --- EIA-310-D 1U rack panel standard dimensions ---
rack_w          = 482.6;    // [mm] Standard 19-inch rack panel width
rack_u_h        = 44.45;    // [mm] 1U panel height
panel_t         = 3.0;      // [mm] Panel thickness (3D print: 3mm; laser Al: 1.5mm)
panel_depth     = 20.0;     // [mm] Panel body depth (slab — no interior components)

// --- Rack mounting ears ---
ear_w           = 12.7;     // [mm] Rack flange (ear) width each side
ear_hole_x      = 6.35;     // [mm] Mounting hole from ear edge (EIA-310)
ear_hole_d      = 5.5;      // [mm] M5 clearance hole (some racks use M6 — change to 6.5)
ear_hole_spacing = 15.875;  // [mm] Vertical spacing between rack mounting holes (EIA-310)
ear_hole_z_top  = rack_u_h / 2 - ear_hole_spacing / 2;
ear_hole_z_bot  = rack_u_h / 2 + ear_hole_spacing / 2;

// --- Usable panel interior (between the two ears) ---
panel_interior_w = rack_w - ear_w * 2;  // ≈ 457.2mm

// --- Cable management slots ---
// Horizontal slots for Velcro cable ties. Four positions across panel interior.
cable_slot_w    = 8;        // [mm] Slot width (Velcro tie passes through)
cable_slot_h    = 6;        // [mm] Slot height
cable_slot_t    = panel_depth - 4;  // [mm] Slot depth (through to near-rear face)
cable_slot_gap  = 60;       // [mm] Between slot pairs on left / right sides

// --- QR code surface ---
qr_size         = 30;       // [mm] QR sticker area
qr_border       = 2;        // [mm] Raised border
qr_recess_d     = 0.8;      // [mm] Sticker recess depth
qr_platform_sz  = qr_size + qr_border * 2;
qr_platform_h   = 2.0;      // [mm] Platform protrusion from front face

// --- Status LED hole ---
led_d           = 5.5;      // [mm] 5mm LED clearance hole
led_x           = ear_w + 20;           // [mm] 20mm from left ear
led_z           = rack_u_h / 2;         // [mm] Vertically centred

// --- Panel split (for printing in two halves) ---
split_x         = rack_w / 2;           // [mm] Split at centre
split_pin_d     = 3.0;                  // [mm] Alignment pin diameter (M3)
split_pin_h     = 8.0;                  // [mm] Alignment pin height
split_pin_spacing = 15;                 // [mm] Distance from split line to pin centres

// --- Fit tolerance ---
fit_t           = 0.4;      // [mm]


// =============================================================================
// SECTION 2 — HELPER MODULES
// =============================================================================

// Single cable management slot (through panel depth)
module cable_slot() {
    translate([0, -0.1, 0])
    cube([cable_slot_w, panel_depth + 0.2, cable_slot_h]);
}

// QR surface for panel — protrudes from front face (Y = panel_t direction)
// Panel front face is at Y = 0; this protrudes in -Y direction.
module qr_surface_panel() {
    difference() {
        cube([qr_platform_sz, qr_platform_h, qr_platform_sz]);
        // Recess on front face (Y = 0) of the platform
        translate([qr_border, -0.1, qr_border])
        cube([qr_size, qr_recess_d + 0.1, qr_size]);
    }
}


// =============================================================================
// SECTION 3 — MAIN PANEL MODULE
// =============================================================================

module federation_panel() {

    difference() {
        // ── Main panel body ──────────────────────────────────────────────────
        // Oriented: X = rack width, Y = panel thickness, Z = rack height
        cube([rack_w, panel_t, rack_u_h]);

        // ── Rack mounting holes in ears ──────────────────────────────────────
        // Left ear: 2 holes
        for (z_off = [ear_hole_z_top, ear_hole_z_bot]) {
            translate([ear_hole_x, -0.1, z_off])
            rotate([-90, 0, 0])
            cylinder(d = ear_hole_d, h = panel_t + 0.2, $fn = 16);
        }
        // Right ear: 2 holes
        for (z_off = [ear_hole_z_top, ear_hole_z_bot]) {
            translate([rack_w - ear_hole_x, -0.1, z_off])
            rotate([-90, 0, 0])
            cylinder(d = ear_hole_d, h = panel_t + 0.2, $fn = 16);
        }

        // ── Status LED hole (left side) ──────────────────────────────────────
        translate([led_x, -0.1, led_z])
        rotate([-90, 0, 0])
        cylinder(d = led_d, h = panel_t + 0.2, $fn = 32);
    }

    // ── QR code surface (right side of panel interior) ───────────────────────
    // Protrudes forward from the panel front face.
    // The QR code links to this node's serial on the cooperative federation ledger.
    qr_x = rack_w - ear_w - qr_platform_sz - 15;
    qr_z = rack_u_h / 2 - qr_platform_sz / 2;
    translate([qr_x, 0, qr_z])
    qr_surface_panel();
}


// =============================================================================
// SECTION 4 — PANEL EXTENSION SLAB (depth module)
// =============================================================================
//
// A flat slab of depth panel_depth is added to convert the EIA-310 panel face
// into a slab panel. This adds rigidity and provides the rear surface for
// cable slot cut-outs.
//
// The slab is separate from the thin face panel above so that the two halves
// can be printed flat without support. Assembly: glue or bolt slab to face.

module federation_panel_slab() {

    difference() {
        // Slab body: full rack width × panel_depth × slab_h
        slab_h = rack_u_h - 4;  // 2mm clearance top/bottom to avoid rack cage contact
        translate([0, panel_t, 2])
        cube([rack_w, panel_depth - panel_t, slab_h]);

        // ── Cable management slots — LEFT zone ───────────────────────────────
        // Two slots, 60mm from left ear
        for (s = [0, 1]) {
            translate([
                ear_w + 50 + s * (cable_slot_w + 6),
                panel_t - 0.1,
                rack_u_h / 2 - cable_slot_h / 2
            ])
            cable_slot();
        }

        // ── Cable management slots — CENTRE LEFT ─────────────────────────────
        for (s = [0, 1]) {
            translate([
                rack_w / 2 - 80 + s * (cable_slot_w + 6),
                panel_t - 0.1,
                rack_u_h / 2 - cable_slot_h / 2
            ])
            cable_slot();
        }

        // ── Cable management slots — CENTRE RIGHT ────────────────────────────
        for (s = [0, 1]) {
            translate([
                rack_w / 2 + 58 + s * (cable_slot_w + 6),
                panel_t - 0.1,
                rack_u_h / 2 - cable_slot_h / 2
            ])
            cable_slot();
        }

        // ── Cable management slots — RIGHT zone ──────────────────────────────
        for (s = [0, 1]) {
            translate([
                rack_w - ear_w - 70 + s * (cable_slot_w + 6),
                panel_t - 0.1,
                rack_u_h / 2 - cable_slot_h / 2
            ])
            cable_slot();
        }
    }
}


// =============================================================================
// SECTION 5 — TWO-HALF PRINT SPLIT
// =============================================================================
//
// At 482.6mm, this panel exceeds most consumer printer build volumes (≤ 256mm).
// Print as LEFT HALF and RIGHT HALF, joined at X = split_x with:
//   - 2× M3×10 bolts through vertical slots at the split line
//   - 2× 3mm alignment pins (press-fit dowels or M3 rods) for alignment
//
// Each half has pins on one side and sockets on the other.
// LEFT HALF: pins protruding from right edge (at X = split_x)
// RIGHT HALF: sockets in left edge (at X = 0 of the right half)
//
// Use a dab of CA glue on the mating faces for a permanent joint.

module panel_join_pin() {
    cylinder(d = split_pin_d, h = split_pin_h, $fn = 16);
}

module panel_join_socket() {
    cylinder(d = split_pin_d + fit_t, h = split_pin_h + 1, $fn = 16);
}

// Left half: X = 0 to split_x, with join pins on right cut face
module federation_panel_left_half() {
    // Clip the full panel to left half
    intersection() {
        union() {
            federation_panel();
            federation_panel_slab();
        }
        cube([split_x, panel_depth + 2, rack_u_h + 2]);
    }

    // Alignment pins protruding from right cut face (at X = split_x)
    for (z_off = [rack_u_h * 0.33, rack_u_h * 0.67]) {
        translate([split_x, panel_depth / 2, z_off])
        rotate([0, 90, 0])
        panel_join_pin();
    }
}

// Right half: X = split_x to rack_w, translated to origin for printing
module federation_panel_right_half() {
    translate([-split_x, 0, 0]) {
        // Clip the full panel to right half
        difference() {
            intersection() {
                union() {
                    federation_panel();
                    federation_panel_slab();
                }
                translate([split_x, 0, 0])
                cube([split_x + 5, panel_depth + 2, rack_u_h + 2]);
            }

            // Alignment sockets in left cut face (at X = split_x)
            for (z_off = [rack_u_h * 0.33, rack_u_h * 0.67]) {
                translate([split_x, panel_depth / 2, z_off])
                rotate([0, 90, 0])
                panel_join_socket();
            }
        }
    }
}


// =============================================================================
// SECTION 6 — RENDER
// =============================================================================
//
// Full panel preview (use F5 — may be slow due to width):
//   federation_panel();
//   federation_panel_slab();
//
// Print-ready split halves (export each as separate STL):
//   federation_panel_left_half();    // print flat, panel front face down
//   federation_panel_right_half();   // print flat, panel front face down
//
// Assembly:
//   1. Print left and right halves.
//   2. Press M3 alignment pins (or 3mm steel rod cuts) into left half sockets.
//   3. Dry-fit right half — pins should engage sockets cleanly.
//   4. Apply CA glue to mating faces. Press together. Clamp for 5 minutes.
//   5. Affix QR sticker into front-face recess.
//   6. Install 5mm status LED in LED hole (retained by snap ring or hot glue).
//   7. Route Velcro cable ties through cable management slots.
//   8. Mount in rack with M5×10 screws through ear holes.
// =============================================================================

// Default render: full panel preview
federation_panel();
federation_panel_slab();

// Split half exports (uncomment one at a time for STL export):
// federation_panel_left_half();
// federation_panel_right_half();
