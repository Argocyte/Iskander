// =============================================================================
// ISKANDER HEARTH — 140mm Fan Adapter v1
// File: fan_140mm_adapter_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
// Phase   : 7 — Thermal & Acoustic Validation
//
// An adapter plate that mounts to the chassis' standard 120mm fan position
// (105mm screw pattern, 115mm aperture) and provides a 140mm fan mount.
//
// USE CASE:
//   The chassis top or rear panel has a 120mm fan position (cut in OpenSCAD
//   with fan_cutout() using fan_size=120, fan_screw_spacing=105).
//   This adapter installs into that position, covering the 120mm hole and
//   providing a new 125mm screw hole pattern for a Noctua NF-A14 PWM (P7-002).
//
// NOCTUA NF-A14 PWM (P7-002) specs:
//   Frame: 140×140mm | Aperture: 135mm | Screw spacing: 124.5mm (≈ 125mm)
//   Max flow: 140.2 m³/h (37% more than NF-A12x25 at equivalent RPM)
//   Max noise: 24.6 dBA vs 22.6 dBA for NF-A12x25
//
// TRADE-OFF:
//   More airflow per dBA at low RPM — better for living room deployment.
//   Requires a 140mm chassis cutout (top panel mod or this adapter + hole enlargement).
//
// PRINT SETTINGS:
//   Material: PETG | Layer: 0.2mm | Perimeters: 4 | Infill: 30% rectilinear
//   Orientation: Flat (plate lying on build surface) — zero supports needed.
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS
// =============================================================================

// --- Chassis 120mm fan position (to mount onto) ---
chassis_fan_size         = 120;    // [mm] Chassis panel fan cutout outer frame
chassis_fan_aperture_d   = 115;    // [mm] Existing chassis fan aperture diameter
chassis_screw_spacing    = 105;    // [mm] Existing chassis screw hole spacing (120mm fan)
chassis_screw_d          = 4.2;    // [mm] M4 clearance for chassis-side screws

// --- 140mm fan to mount on adapter ---
fan_140_size             = 140;    // [mm] NF-A14 frame
fan_140_aperture_d       = 135;    // [mm] NF-A14 clear airflow aperture
fan_140_screw_spacing    = 124.5;  // [mm] NF-A14 screw hole spacing (125mm nominal)
fan_140_screw_d          = 4.2;    // [mm] M4 clearance for fan-side screws

// --- Adapter plate ---
adapter_t                = 4.0;    // [mm] Plate thickness (rigid, ≥ 4mm)
adapter_margin           = 8;      // [mm] Extra material beyond 140mm fan frame

// --- Derived ---
adapter_size             = fan_140_size + adapter_margin * 2;  // Total plate size
chassis_screw_half       = chassis_screw_spacing / 2;
fan_140_screw_half       = fan_140_screw_spacing / 2;


// =============================================================================
// SECTION 2 — MODULES
// =============================================================================

module fan_140mm_adapter() {
    difference() {
        // Adapter body — square plate, centred at origin
        translate([-adapter_size / 2, -adapter_size / 2, 0])
        cube([adapter_size, adapter_size, adapter_t]);

        // ── Central airflow aperture ───────────────────────────────────────────
        // Sized to 140mm fan aperture — this is the dominant flow path.
        // The existing 120mm chassis hole is fully contained within this opening.
        translate([0, 0, -0.1])
        cylinder(d = fan_140_aperture_d, h = adapter_t + 0.2, $fn = 64);

        // ── 120mm chassis-side screw holes (attach adapter to chassis) ────────
        // These align with the existing 105mm screw pattern in the chassis panel.
        for (sx = [-chassis_screw_half, chassis_screw_half]) {
            for (sy = [-chassis_screw_half, chassis_screw_half]) {
                translate([sx, sy, -0.1])
                cylinder(d = chassis_screw_d, h = adapter_t + 0.2, $fn = 16);
            }
        }

        // ── 140mm fan-side screw holes (attach NF-A14 to adapter) ─────────────
        // 125mm screw pattern for Noctua NF-A14.
        // These are countersunk: M4 pan-head sits flush with adapter top face.
        for (sx = [-fan_140_screw_half, fan_140_screw_half]) {
            for (sy = [-fan_140_screw_half, fan_140_screw_half]) {
                // Clearance hole through full thickness
                translate([sx, sy, -0.1])
                cylinder(d = fan_140_screw_d, h = adapter_t + 0.2, $fn = 16);

                // Countersink (M4 pan-head: 8mm head diameter, 2.5mm head height)
                translate([sx, sy, adapter_t - 2.5])
                cylinder(d1 = fan_140_screw_d, d2 = 8.5, h = 2.6, $fn = 16);
            }
        }

        // ── Lightening holes ──────────────────────────────────────────────────
        // Reduce mass without compromising rigidity.
        // Placed in the 4 corner zones between screw holes, clear of all holes.
        for (lx = [-1, 1]) {
            for (ly = [-1, 1]) {
                translate([lx * (adapter_size / 2 - 15), ly * (adapter_size / 2 - 15), -0.1])
                cylinder(d = 14, h = adapter_t + 0.2, $fn = 32);
            }
        }
    }

    // Embossed label: "120→140 ADAPTER" on top face
    // Uncomment when font is available:
    // translate([-25, -adapter_size/2 + 4, adapter_t])
    // linear_extrude(height = 0.8)
    // text("120→140 ADAPTER", size = 5, font = "Liberation Sans:style=Bold");
}


// =============================================================================
// SECTION 3 — FAN ALIGNMENT GUIDE
// Prints a positioning jig to drill the correct 140mm hole in an existing panel.
// Uncomment to render.
// =============================================================================

// module drill_guide() {
//     difference() {
//         // Guide ring: sits inside the existing 115mm aperture
//         cylinder(d = chassis_fan_aperture_d - 1, h = 6, $fn = 64);
//         // Mark the 125mm screw positions
//         for (sx = [-fan_140_screw_half, fan_140_screw_half]) {
//             for (sy = [-fan_140_screw_half, fan_140_screw_half]) {
//                 translate([sx, sy, -0.1])
//                 cylinder(d = 2.5, h = 7, $fn = 16);  // 2.5mm pilot hole markers
//             }
//         }
//         // Centre mark
//         translate([0, 0, -0.1]) cylinder(d = 3, h = 7, $fn = 16);
//     }
// }


// =============================================================================
// SECTION 4 — RENDER
// =============================================================================

fan_140mm_adapter();

// drill_guide();   // <-- uncomment to print alignment jig separately

// Ghost overlays for design verification:
// %translate([0, 0, adapter_t]) color("silver", 0.2)
//   cube([fan_140_size, fan_140_size, 25], center = true);  // NF-A14 ghost
// %color("navy", 0.15)
//   cylinder(d = chassis_fan_aperture_d, h = 4, $fn = 64);  // 120mm chassis aperture
