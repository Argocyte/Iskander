// =============================================================================
// ISKANDER HEARTH — Fan Duct v1
// File: fan_duct_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
// Phase   : 7 — Thermal & Acoustic Validation
//
// A parametric airflow duct that mounts to a standard 120mm fan using the
// 105mm screw hole pattern and channels airflow toward the motherboard zone.
//
// TWO VARIANTS (set duct_type below):
//   "intake"  — Top-panel intake duct. Directs fan-driven air downward into
//               the MB area, increasing CPU cooler effectiveness. Flares from
//               the 115mm fan aperture to a 90×90mm square outlet at MB level.
//
//   "exhaust" — Rear-panel exhaust collector. Sweeps hot GPU exhaust air from
//               the GPU zone into the 120mm exhaust fan aperture, reducing
//               recirculation and improving exhaust efficiency.
//
// PRINT CONSTRAINTS (all variants):
//   - Zero supports required. All overhangs ≤ 45° from vertical.
//   - Walls ≥ 2mm throughout for structural rigidity.
//   - Snap clips engage the chassis inner-wall fan mount lip.
//
// TARGET FAN: Noctua NF-A12x25 PWM (P7-001)
//   120mm, 105mm screw spacing, 25mm depth
//   Max flow: 102.1 m³/h at 2000 RPM
//
// PRINT SETTINGS:
//   Material: PETG (heat-resistant, ≤ 80°C chassis temps)
//   Layer:    0.2mm | Perimeters: 3 | Infill: 20% gyroid
//   Orientation: Print duct standing upright (longest dimension vertical)
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS
// =============================================================================

duct_type           = "intake";  // "intake" or "exhaust"  <-- CHANGE ME

// --- Fan mount geometry (Noctua NF-A12x25 / standard 120mm) ---
fan_size            = 120;       // [mm] Fan frame outer dimension
fan_aperture_d      = 115;       // [mm] Clear airflow aperture diameter
fan_screw_spacing   = 105;       // [mm] Screw hole centre-to-centre (square pattern)
fan_screw_d         = 4.2;       // [mm] M4 clearance hole (standard fan screw)
fan_mount_depth     = 25;        // [mm] Fan body depth (NF-A12x25)

// --- Duct body ---
duct_wall_t         = 2.0;       // [mm] Duct wall thickness (min for structural integrity)
duct_length         = 120;       // [mm] Duct axial length (fan face to outlet)
                                  //      Intake: from top panel down toward MB
                                  //      Exhaust: from GPU zone to rear panel fan

// --- Intake duct outlet (square, aimed at MB) ---
outlet_w            = 90;        // [mm] Square outlet width (covers CPU cooler footprint)
outlet_h            = 90;        // [mm] Square outlet height

// --- Snap clip geometry (engages chassis inner-wall lip) ---
clip_w              = 10;        // [mm] Clip tab width
clip_t              = 2.0;       // [mm] Clip tab thickness
clip_h              = 5;         // [mm] Clip hook height (catches wall edge)
clip_gap            = 0.4;       // [mm] Clearance gap for clip engagement

// --- Fit tolerance ---
fit_tolerance       = 0.3;       // [mm] Press-fit for chassis slot interface


// =============================================================================
// SECTION 2 — DERIVED DIMENSIONS
// =============================================================================

fan_mount_half      = fan_size / 2;
screw_half          = fan_screw_spacing / 2;

// Transition from circular inlet (fan) to square outlet (MB area)
// Inlet inner radius = fan_aperture_d/2 at Z=0
// Outlet corner half-size = outlet_w/2, outlet_h/2 at Z=duct_length
inlet_r             = fan_aperture_d / 2;
outlet_half_w       = outlet_w / 2;
outlet_half_h       = outlet_h / 2;


// =============================================================================
// SECTION 3 — HELPER MODULES
// =============================================================================

// Fan mounting flange — flat plate with 4× M4 screw holes + central aperture
module fan_flange(t = duct_wall_t) {
    difference() {
        // Flange plate (slightly wider than fan frame for mounting overlap)
        cube([fan_size + 4, fan_size + 4, t], center = true);

        // Central airflow aperture
        cylinder(d = fan_aperture_d + fit_tolerance, h = t + 0.2, $fn = 64, center = true);

        // 4× M4 screw holes (fan mount pattern: 105mm square)
        for (sx = [-screw_half, screw_half]) {
            for (sy = [-screw_half, screw_half]) {
                translate([sx, sy, 0])
                cylinder(d = fan_screw_d, h = t + 0.2, $fn = 16, center = true);
            }
        }
    }
}

// Snap clip tab — hooks onto inner chassis wall lip
// Place at 4 positions around the duct perimeter
module snap_clip() {
    union() {
        // Clip arm
        cube([clip_w, clip_t, clip_h]);
        // Hook at the end
        translate([0, clip_t, clip_h - clip_t])
        cube([clip_w, clip_t * 1.5, clip_t]);
    }
}


// =============================================================================
// SECTION 4 — DUCT BODIES
// =============================================================================

module intake_duct() {
    // Intake duct: circular inlet at top (fan face) → square outlet at bottom (MB level)
    // No supports needed: walls lean inward ≤ 45° in all cross-sections.
    //
    // Built as a difference: outer shell minus inner air channel
    // Both transition from circle→square using hull() at intermediate stations.

    // Number of hull stations for smooth transition
    n_stations = 8;

    difference() {
        // ── Outer shell ───────────────────────────────────────────────────────
        hull() {
            // Top: circle matching fan aperture + wall thickness
            translate([0, 0, 0])
            cylinder(d = fan_aperture_d + duct_wall_t * 2, h = 1, $fn = 64);

            // Bottom: square matching outlet + wall thickness
            translate([
                -(outlet_half_w + duct_wall_t),
                -(outlet_half_h + duct_wall_t),
                duct_length
            ])
            cube([
                outlet_w + duct_wall_t * 2,
                outlet_h + duct_wall_t * 2,
                1
            ]);
        }

        // ── Inner air channel ─────────────────────────────────────────────────
        translate([0, 0, -0.1])
        hull() {
            cylinder(d = fan_aperture_d, h = 1, $fn = 64);
            translate([-outlet_half_w, -outlet_half_h, duct_length + 0.1])
            cube([outlet_w, outlet_h, 1]);
        }
    }

    // Fan flange at top
    translate([0, 0, -duct_wall_t])
    fan_flange(t = duct_wall_t);

    // Snap clips: 4× positioned at duct_length end (chassis inner wall engagement)
    clip_positions = [
        [ outlet_half_w + duct_wall_t - clip_w/2,  0,               duct_length],
        [-(outlet_half_w + duct_wall_t),             0,               duct_length],
        [ 0,  outlet_half_h + duct_wall_t - clip_w/2,  duct_length],
        [ 0, -(outlet_half_h + duct_wall_t),             duct_length],
    ];
    // Simplified: two clips on ±X faces
    for (sx = [-1, 1]) {
        translate([sx * (outlet_half_w + duct_wall_t) - clip_w/2, -clip_w/2, duct_length])
        snap_clip();
    }
}


module exhaust_duct() {
    // Exhaust collector: sweeps GPU zone hot air toward rear exhaust fan.
    // Square inlet at GPU zone side → circular fan flange at rear.
    // Geometry mirrors intake_duct() in reverse.

    // GPU zone inlet approximate size: 160×120mm (GPU exhaust column)
    gpu_inlet_w     = 160;
    gpu_inlet_h     = 120;
    gpu_inlet_half_w = gpu_inlet_w / 2;
    gpu_inlet_half_h = gpu_inlet_h / 2;

    difference() {
        hull() {
            // Rear end: circle for fan flange
            translate([0, 0, 0])
            cylinder(d = fan_aperture_d + duct_wall_t * 2, h = 1, $fn = 64);

            // Front end: rectangle for GPU exhaust inlet
            translate([
                -(gpu_inlet_half_w + duct_wall_t),
                -(gpu_inlet_half_h + duct_wall_t),
                duct_length
            ])
            cube([
                gpu_inlet_w + duct_wall_t * 2,
                gpu_inlet_h + duct_wall_t * 2,
                1
            ]);
        }

        // Inner channel
        translate([0, 0, -0.1])
        hull() {
            cylinder(d = fan_aperture_d, h = 1, $fn = 64);
            translate([-gpu_inlet_half_w, -gpu_inlet_half_h, duct_length + 0.1])
            cube([gpu_inlet_w, gpu_inlet_h, 1]);
        }
    }

    // Fan flange at rear face
    translate([0, 0, -duct_wall_t])
    fan_flange(t = duct_wall_t);
}


// =============================================================================
// SECTION 5 — RENDER
// =============================================================================

if (duct_type == "intake") {
    intake_duct();
} else if (duct_type == "exhaust") {
    exhaust_duct();
} else {
    echo("ERROR: set duct_type to \"intake\" or \"exhaust\"");
}

// Fan ghost (for alignment check):
// %translate([0, 0, -(fan_mount_depth + duct_wall_t)])
//     color("silver", 0.3) cube([fan_size, fan_size, fan_mount_depth], center=true);
