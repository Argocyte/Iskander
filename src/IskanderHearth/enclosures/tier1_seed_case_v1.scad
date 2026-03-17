// =============================================================================
// ISKANDER HEARTH — Tier 1 Seed Node Glass Box Attachment v1
// File: tier1_seed_case_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
//           https://ohwr.org/cern_ohl_s_v2.txt
// Phase   : 8 — Distributed Cooperative Manufacturing
//
// WHAT THIS IS:
//   Tier 1 uses a refurbished N100 Mini PC or equivalent 1L SFF computer.
//   These machines have no internal expansion — the Solidarity HAT cannot be
//   installed inside the host. This file defines a compact EXTERNAL enclosure
//   that houses the Solidarity HAT PCB and provides the full Glass Box UX
//   (HITL buttons + NeoPixel status strip) as a standalone desktop accessory.
//
//   The enclosure sits alongside the mini PC, connected via:
//     - USB-I2C bridge cable (I2C to HAT: INA3221 + ATECC608B)
//     - USB-A to HAT GPIO header adapter (kill switch GPIO, button GPIO)
//     - USB-C power input (5V from host or wall adapter)
//
// CONTENTS:
//   Solidarity HAT PCB (65×56mm, 1.6mm FR4, 4 M3 standoffs at corners)
//   2× Sanwa OBSA-30 arcade buttons (Veto / Sign) on front face
//   WS2812B NeoPixel strip (30 LEDs, 0.5m, trimmed to 150mm for this case)
//   3mm frosted acrylic diffuser panel (top window, 140×12mm)
//   JST-XH cable exit on rear for USB-I2C + USB-C power
//   3× toggle switches (Mic / Wi-Fi / GPU kill) on rear panel
//
// FORM FACTOR:
//   Footprint: 160×90mm (fits on desk beside any 1L Mini PC)
//   Height: 60mm (shorter than a stack of 3 paperback books)
//   Style: Two-part (base + lid) — lid lifts vertically, retained by M3 clips
//
// PRINT SETTINGS:
//   Material : PETG (black, grey, or natural)
//   Layer    : 0.2mm
//   Perimeters: 3
//   Infill   : 30% gyroid
//   Supports : No supports needed — all features designed for flat print orientation
//   Orientation: Base lies on build surface (flat). Lid lies on build surface (flat).
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS
// =============================================================================

// --- Solidarity HAT PCB ---
hat_w           = 65.0;     // [mm] HAT PCB width
hat_d           = 56.0;     // [mm] HAT PCB depth
hat_pcb_t       = 1.6;      // [mm] PCB thickness (FR4)
hat_hole_inset  = 2.5;      // [mm] M3 mounting hole from PCB edge
hat_hole_d      = 3.2;      // [mm] M3 clearance diameter
hat_standoff_h  = 6.0;      // [mm] Standoff height (clears J1 through-hole pins)
hat_standoff_od = 5.0;      // [mm] Standoff OD

// --- Enclosure body ---
wall_t          = 3.0;      // [mm] Wall thickness
base_margin_x   = 12;       // [mm] Margin beyond HAT on X (room for buttons + side walls)
base_margin_y   = 10;       // [mm] Margin beyond HAT on Y (clearance for connectors)
lid_h           = 25;       // [mm] Lid height above base top face (PCB components clearance)

// Derived interior and exterior dimensions
int_w = hat_w + base_margin_x * 2;         // Interior width  = 65 + 24 = 89mm
int_d = hat_d + base_margin_y * 2;         // Interior depth  = 56 + 20 = 76mm
int_h_base = hat_standoff_h + hat_pcb_t;   // Base interior height (to PCB top face) ≈ 7.6mm

ext_w = int_w + wall_t * 2;                // Exterior width  ≈ 95mm
ext_d = int_d + wall_t * 2;                // Exterior depth  ≈ 82mm
ext_h_base = int_h_base + wall_t * 2;      // Base box total height ≈ 14mm (tray)
ext_h_lid  = lid_h + wall_t;               // Lid total height ≈ 28mm

// Combined exterior height (base + lid assembled)
ext_h_total = ext_h_base + ext_h_lid;      // ≈ 42mm (trim if larger than 60mm target)

// --- HITL Buttons (Sanwa OBSA-30) ---
btn_mount_d     = 30.0;     // [mm] Mounting hole diameter
btn_clear_d     = 31.5;     // [mm] Clearance hole (+ fit tolerance)
btn_spacing     = 44.0;     // [mm] Centre-to-centre between buttons
fit_t           = 0.4;      // [mm] General fit tolerance

// --- NeoPixel diffuser window (top lid, trimmed 150mm strip) ---
diffuser_w      = 150;      // [mm] Trimmed NeoPixel strip length for this case
diffuser_h      = 12;       // [mm] Diffuser window height (covers 10mm strip + 1mm each side)
diffuser_t      = 3;        // [mm] 3mm frosted acrylic

// --- Kill switches (rear panel, 3× SPDT toggle, M12 mount) ---
ks_mount_d      = 12.5;     // [mm] M12 toggle switch mounting hole clearance
ks_spacing      = 22;       // [mm] Centre-to-centre spacing between kill switches
ks_row_z        = ext_h_base + lid_h * 0.5; // [mm] Centred on rear panel height

// --- Wire exit port (rear panel) ---
wire_port_w     = 20;       // [mm] Wide slot for USB-I2C + USB-C cable bundle
wire_port_h     = 12;       // [mm] Height of slot

// --- Lid retention clips ---
clip_w          = 6;        // [mm] Clip tab width
clip_h          = 4;        // [mm] Clip tab height (engages lid rim)
clip_inset      = 8;        // [mm] Distance from corner to clip tab centre

// --- Rubber foot recesses (base bottom face) ---
foot_d          = 12;       // [mm] Adhesive rubber foot diameter (self-adhesive bumpon)
foot_inset      = 10;       // [mm] Distance from corner to foot centre

// --- QR surface (left side of lid) ---
qr_size         = 22;       // [mm] QR sticker area (compact — smaller than chassis v1)
qr_border       = 1.5;      // [mm] Raised border around recess
qr_recess_d     = 0.6;      // [mm] Recess depth for sticker

qr_platform_w   = qr_size + qr_border * 2;
qr_platform_h_3d = 2.5;     // [mm] Platform protrusion height


// =============================================================================
// SECTION 2 — HELPER MODULES
// =============================================================================

// M3 standoff (printed — tap after printing, or press-fit M3 heat-set insert)
module hat_standoff() {
    difference() {
        cylinder(d = hat_standoff_od, h = hat_standoff_h, $fn = 16);
        translate([0, 0, -0.1])
        cylinder(d = 2.5, h = hat_standoff_h + 0.2, $fn = 16);  // 2.5mm = M3 tap drill
    }
}

// Small QR surface for compact case lid exterior
module qr_surface_compact() {
    difference() {
        cube([qr_platform_w, qr_platform_w, qr_platform_h_3d]);
        translate([qr_border, qr_border, qr_platform_h_3d - qr_recess_d])
        cube([qr_size, qr_size, qr_recess_d + 0.1]);
    }
}

// Rubber foot recess on bottom face
module foot_recess() {
    cylinder(d = foot_d + 1, h = 2, $fn = 32);
}


// =============================================================================
// SECTION 3 — BASE MODULE
// =============================================================================
//
// The base is a shallow tray (open at top) that holds the Solidarity HAT PCB
// on four printed standoffs. The HAT is secured by M3×5 screws threading into
// the standoffs (tap M3 after printing, or use M3 heat-set inserts).
//
// The base clips to the lid from below. Four clip tabs on the interior rim
// engage matching notches in the lid's lower edge.

module seed_case_base() {

    // HAT PCB mounting hole positions (relative to base interior origin)
    hat_x_off = base_margin_x;  // HAT sits flush with interior margin
    hat_y_off = base_margin_y;
    hat_holes = [
        [hat_x_off + hat_hole_inset,         hat_y_off + hat_hole_inset],
        [hat_x_off + hat_w - hat_hole_inset, hat_y_off + hat_hole_inset],
        [hat_x_off + hat_hole_inset,         hat_y_off + hat_d - hat_hole_inset],
        [hat_x_off + hat_w - hat_hole_inset, hat_y_off + hat_d - hat_hole_inset],
    ];

    difference() {
        // Base tray exterior body
        cube([ext_w, ext_d, ext_h_base]);

        // Hollow interior
        translate([wall_t, wall_t, wall_t])
        cube([int_w, int_d, int_h_base + 0.2]);

        // Rubber foot recesses on bottom face
        for (fx = [foot_inset, ext_w - foot_inset]) {
            for (fy = [foot_inset, ext_d - foot_inset]) {
                translate([fx, fy, wall_t - 2])
                foot_recess();
            }
        }
    }

    // HAT standoffs — 4× printed standoff at hole positions
    for (pos = hat_holes) {
        translate([wall_t + pos[0], wall_t + pos[1], wall_t])
        hat_standoff();
    }
}


// =============================================================================
// SECTION 4 — LID MODULE
// =============================================================================
//
// The lid slides down over the base and is retained by four spring clips
// (two on front, two on rear). A diffuser window slot on the top face accepts
// the trimmed 150mm NeoPixel strip behind 3mm frosted acrylic.
//
// Front face: 2× 30mm button holes (Veto left, Sign right), centred vertically.
// Rear face: 3× M12 kill-switch holes + wire exit port.
// Left face: compact QR surface (links to repair guide) — embossed on exterior.
// Right face: ventilation slots (passive airflow for HAT voltage regulators).

module seed_case_lid() {

    // Button position Z (centred on lid front face height)
    btn_z = lid_h * 0.5;

    // Kill switch row: centred on rear face height
    ks_centre_x = ext_w / 2;  // x-centre of rear face
    ks_z = lid_h * 0.5;

    difference() {
        // Lid exterior body (open at bottom, closed at top)
        cube([ext_w, ext_d, ext_h_lid]);

        // Interior hollow (lid is a capped tube, open at bottom)
        translate([wall_t, wall_t, wall_t])
        cube([int_w, int_d, ext_h_lid + 0.1]);

        // ── NeoPixel diffuser window — top face ──────────────────────────────
        // Centred on top, 150mm × 12mm slot for 3mm acrylic diffuser
        translate([ext_w / 2 - diffuser_w / 2, ext_d / 2 - diffuser_h / 2, ext_h_lid - wall_t - 0.1])
        cube([diffuser_w, diffuser_h, wall_t + 0.2]);

        // ── Front face: Veto button (left) ───────────────────────────────────
        translate([ext_w / 2 - btn_spacing / 2, -0.1, btn_z])
        rotate([-90, 0, 0])
        cylinder(d = btn_clear_d + fit_t, h = wall_t + 0.2, $fn = 64);

        // ── Front face: Sign button (right) ──────────────────────────────────
        translate([ext_w / 2 + btn_spacing / 2, -0.1, btn_z])
        rotate([-90, 0, 0])
        cylinder(d = btn_clear_d + fit_t, h = wall_t + 0.2, $fn = 64);

        // ── Rear face: 3× kill-switch holes ──────────────────────────────────
        for (i = [-1, 0, 1]) {
            translate([ks_centre_x + i * ks_spacing, ext_d - wall_t - 0.1, ks_z])
            rotate([90, 0, 0])
            cylinder(d = ks_mount_d, h = wall_t + 0.2, $fn = 32);
        }

        // ── Rear face: USB/I2C wire exit port ────────────────────────────────
        translate([ext_w / 2 - wire_port_w / 2, ext_d - wall_t - 0.1, wall_t + 2])
        cube([wire_port_w, wall_t + 0.2, wire_port_h]);

        // ── Right face: passive ventilation slots (3 slots) ──────────────────
        slot_w   = 3;
        slot_len = lid_h * 0.6;
        slot_gap = 5;
        slot_start_y = ext_d * 0.3;
        for (n = [0 : 2]) {
            translate([ext_w - wall_t - 0.1, slot_start_y + n * (slot_w + slot_gap), lid_h * 0.2])
            cube([wall_t + 0.2, slot_w, slot_len]);
        }

        // ── Lid retention notches (base clip engagement) ──────────────────────
        // Front: 2 notches
        for (side = [clip_inset, ext_w - clip_inset - clip_w]) {
            translate([side, -0.1, -0.1])
            cube([clip_w, wall_t + 0.1, clip_h + 0.1]);
        }
        // Rear: 2 notches
        for (side = [clip_inset, ext_w - clip_inset - clip_w]) {
            translate([side, ext_d - wall_t - 0.1, -0.1])
            cube([clip_w, wall_t + 0.1, clip_h + 0.1]);
        }
    }

    // ── QR surface — left face exterior ──────────────────────────────────────
    // Mounted flush with left wall, centred in lid height
    translate([
        -qr_platform_h_3d,
        ext_d / 2 - qr_platform_w / 2,
        lid_h / 2 - qr_platform_w / 2
    ])
    rotate([0, -90, 0])
    qr_surface_compact();
}


// =============================================================================
// SECTION 5 — ASSEMBLY (EXPLODED OR ASSEMBLED)
// =============================================================================

module seed_case_assembled() {
    // Base at Z=0
    seed_case_base();

    // Lid sits directly on top of base (base top face = Z = ext_h_base)
    translate([0, 0, ext_h_base])
    seed_case_lid();
}


// =============================================================================
// SECTION 6 — RENDER
// =============================================================================
//
// Default: render base only (for first print).
// Uncomment the desired output below.
//
// PRINT GUIDE:
//   Print base and lid as separate STL files. Both print flat (no supports).
//   After printing:
//     1. Tap M3 threads in standoff holes (2.5mm pilot already in place).
//        OR: press-fit M3 heat-set inserts with soldering iron at 200°C.
//     2. Mount Solidarity HAT PCB on standoffs with M3×5 screws.
//     3. Route I2C + GPIO wiring through rear wire exit port.
//     4. Install kill switches in rear panel M12 holes (nut retains from inside).
//     5. Install Sanwa OBSA-30 buttons through front face holes (nut retains from inside).
//     6. Slide NeoPixel strip into top diffuser slot. Press 3mm acrylic in from end.
//     7. Lower lid over base. Spring clips snap into base notches.
// =============================================================================

// Render individual parts (export each separately for printing):
seed_case_base();

// seed_case_lid();              // <-- uncomment to export lid

// seed_case_assembled();        // <-- uncomment to preview assembled case

// HAT PCB ghost (for clearance check):
// %translate([wall_t + base_margin_x, wall_t + base_margin_y, wall_t + hat_standoff_h])
//   cube([hat_w, hat_d, hat_pcb_t]);

// NeoPixel strip ghost (top diffuser slot):
// %translate([ext_w/2 - diffuser_w/2, ext_d/2 - 10/2, ext_h_base + ext_h_lid - wall_t])
//   cube([diffuser_w, 10, 3]);
