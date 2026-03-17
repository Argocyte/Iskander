// =============================================================================
// ISKANDER HEARTH — Tier 2 Commons Node Chassis v1
// File: hearth_chassis_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
//           https://ohwr.org/cern_ohl_s_v2.txt
// Project : https://github.com/iskander-os/iskander-hearth
// =============================================================================
//
// WHAT THIS FILE IS
//   A parametric 3D model of the Iskander Hearth Tier 2 Commons Node chassis.
//   Fits: Mini-ITX motherboard | SFX or ATX PSU | dual-slot GPU up to 240mm
//
//   This script can be used to:
//     (A) 3D-PRINT individual panels in PETG or ASA
//         — Recommended settings: 3 perimeters, 40% gyroid infill, 0.2mm layer
//     (B) LASER-CUT flat panels from 3mm acrylic or birch plywood
//         — Use projection(cut=true) in OpenSCAD to generate DXF outlines
//     (C) VISUALISE component clearances before buying parts
//
// HOW TO USE
//   1. Install OpenSCAD (free): https://openscad.org/downloads.html
//   2. Open this file. Press F5 to preview. Press F6 to render fully.
//   3. Edit any value in SECTION 1 below.
//   4. Press F6, then File > Export > Export as STL  (for 3D printing)
//                               OR Export as DXF  (for laser cutting a panel)
//
// NON-ENGINEER QUICK START
//   You only need to care about SECTION 1. Look for lines with <-- CHANGE ME.
//   Everything else is calculated automatically.
//
// CHASSIS LAYOUT (viewed from the front, left side open)
//
//   ┌──────────────────────────────────┐  ← Top panel  (120mm intake fan)
//   │  [PSU — rear-top]                │
//   │  [CPU Cooler + Motherboard]      │  ← MB tray on right side panel
//   │  [GPU — front-bottom]            │  ← PCIe from MB, points toward front
//   │  [2× SSD bays — front-bottom]    │
//   └──────────────────────────────────┘  ← Bottom panel (rubber feet)
//     ↑ Front panel                   ↑ Rear panel
//     (power btn, USB, intake vents)     (I/O shield, PCIe brackets, PSU inlet, exhaust fan)
//
// =============================================================================


// =============================================================================
// SECTION 1 — PARAMETERS (THE ONLY SECTION YOU NEED TO EDIT)
// =============================================================================

// --- Wall & Panel Thickness ---
wall_thickness = 3;         // [mm]  Panel thickness.
                            //       3mm = suitable for laser cutting.
                            //       4mm = recommended for 3D printing.
                            //       <-- CHANGE ME to match your material

// --- Mini-ITX Motherboard ---
// Standard Mini-ITX is always 170 × 170mm. Do not change unless
// you are building for a different form factor.
mb_width            = 170;  // [mm]  Mini-ITX PCB width  (X axis)
mb_depth            = 170;  // [mm]  Mini-ITX PCB depth  (Y axis)
mb_pcb_t            = 1.6;  // [mm]  PCB thickness (standard FR4)
mb_standoff_h       = 6.5;  // [mm]  Brass standoff height (M3 standard)
                            //       Standoff hole pattern: 154.94 × 154.94mm from corner
                            //       Inset: 6.35mm from PCB edge to hole centre

// --- CPU Cooler ---
cpu_cooler_max_h    = 58;   // [mm]  Maximum cooler height above MB surface.
                            //       Noctua NH-L9a-AM5 = 37mm. This chassis accepts up to 58mm.
                            //       <-- CHANGE ME if your cooler is shorter (saves height)

// --- GPU ---
gpu_length          = 240;  // [mm]  Maximum GPU length (depth, front-to-back).
                            //       RTX 3060 Founders = 242mm, XC = 200mm.
                            //       <-- CHANGE ME to match your specific card (saves depth)
gpu_slot_width      = 40;   // [mm]  Dual-slot GPU PCB + cooler width. Do not reduce below 40.
gpu_height          = 111;  // [mm]  GPU card height (PCIe bracket bottom to top of cooler).
gpu_clearance_mm    = 12;   // [mm]  Minimum airflow gap below GPU cooler fins.
                            //       Increase to 16mm if GPU thermals are a concern.
                            //       <-- CHANGE ME for hotter cards

// --- Power Supply (SFX default) ---
// SFX PSU fits a Mini-ITX chassis. If you must use a standard ATX PSU,
// swap in the ATX dimensions below.
psu_w               = 125;  // [mm]  SFX PSU width  | ATX = 150
psu_d               = 100;  // [mm]  SFX PSU depth  | ATX = 140
psu_h               = 63.5; // [mm]  SFX PSU height | ATX = 86
                            //       <-- CHANGE ME to 150 / 140 / 86 for a standard ATX PSU

// --- 2.5-inch SSD Drive Bays ---
ssd_w               = 70;   // [mm]  2.5-inch SSD width
ssd_d               = 100;  // [mm]  2.5-inch SSD depth
ssd_h               = 9;    // [mm]  SSD height (7mm drive + 2mm mounting bracket)
ssd_bay_count       = 2;    // [qty] Number of stacked SSD bays
ssd_bay_gap         = 3;    // [mm]  Vertical gap between stacked SSD brackets

// --- Fans ---
fan_size            = 120;  // [mm]  Fan diameter. 120mm is standard. 140mm requires chassis mod.
fan_screw_spacing   = 105;  // [mm]  Centre-to-centre distance between fan screw holes (120mm fan)

// --- QR Code Repair Surfaces (Framework-style) ---
// Three embossed 30×30mm surfaces are placed on interior walls near:
//   (1) GPU bay  →  left side panel interior
//   (2) PSU bay  →  right side panel interior, upper
//   (3) SSD bay  →  right side panel interior, lower
// Users stick or insert a QR code sticker/tile into the recessed area.
// QR codes should link to the component's entry in boms/tier2_commons.md.
qr_size             = 30;   // [mm]  QR code sticker area (square). 30×30mm = Framework standard.
qr_recess_depth     = 0.8;  // [mm]  Depth of recess to hold the sticker flush. ~0.6–1.0mm.
qr_border           = 2;    // [mm]  Raised border around the recess on the platform.
                            //       <-- CHANGE ME if sticker alignment is difficult

// --- Ventilation Slots ---
vent_slot_w         = 3;    // [mm]  Width of each ventilation slot
vent_slot_gap       = 4;    // [mm]  Gap between adjacent slots
vent_slot_len       = 60;   // [mm]  Length of each slot

// --- Print/Cut Tolerances ---
fit_tolerance       = 0.4;  // [mm]  Added to component cutout dimensions.
                            //       Increase to 0.6 if prints are tight.
                            //       Decrease to 0.2 for laser-cut acrylic (tighter kerf).


// =============================================================================
// SECTION 2 — DERIVED DIMENSIONS (DO NOT EDIT — calculated automatically)
// =============================================================================

// Vertical height occupied by each component zone inside the chassis
mb_zone_h    = mb_standoff_h + mb_pcb_t + cpu_cooler_max_h;
// e.g.  6.5 + 1.6 + 58 = 66.1mm

gpu_zone_h   = gpu_height + gpu_clearance_mm;
// e.g.  111 + 12 = 123mm

ssd_zone_h   = ssd_bay_count * ssd_h + (ssd_bay_count - 1) * ssd_bay_gap;
// e.g.  2 × 9 + 1 × 3 = 21mm

// Internal chassis dimensions (inside the walls)
int_w = mb_width + psu_w + wall_thickness * 3 + 20;
//     MB width + PSU width + inter-component wall + margins
//     = 170 + 125 + 9 + 20 = 324mm

int_d = gpu_length + 30;
//     GPU length + rear cable-management gap
//     = 240 + 30 = 270mm

int_h = mb_zone_h + gpu_zone_h + ssd_zone_h + 40;
//     MB zone + GPU zone + SSD zone + vertical margins
//     = 66 + 123 + 21 + 40 = 250mm  (approximate)

// External chassis dimensions (outer face to outer face)
ext_w = int_w + wall_thickness * 2;
ext_d = int_d + wall_thickness * 2;
ext_h = int_h + wall_thickness * 2;

// Mini-ITX standard constants (PCIe specification)
mb_hole_inset    = 6.35;    // [mm]  From PCB edge to mounting hole centre
mb_hole_pattern  = 154.94;  // [mm]  Hole pattern size (square)
io_shield_w      = 158.76;  // [mm]  I/O shield opening width  (Mini-ITX spec)
io_shield_h      = 44.45;   // [mm]  I/O shield opening height (Mini-ITX spec)
pcie_from_mb_top = 149.86;  // [mm]  PCIe slot centre from top of MB (Mini-ITX spec)

// QR platform total footprint (recess + border)
qr_platform = qr_size + qr_border * 2;  // = 30 + 4 = 34mm square
qr_platform_h = 2.5;                     // [mm]  How far platform protrudes from wall interior


// =============================================================================
// SECTION 3 — HELPER MODULES
// Reusable building blocks called by the panel modules in Section 4.
// You do not need to edit these unless you want to change generic shapes.
// =============================================================================

// --- Ventilation Grid ---
// Creates a grid of rectangular airflow slots.
//
//   Parameters
//   grid_w : total width of the vent field
//   grid_h : total height of the vent field
//   depth  : how deep to cut (set to wall_thickness + 0.2 for a through-cut)
//
module vent_grid(grid_w, grid_h, depth) {
    col_step = vent_slot_w + vent_slot_gap;   // step between slot columns
    row_step = vent_slot_len + vent_slot_gap; // step between slot rows
    cols = floor(grid_w / col_step);
    rows = floor(grid_h / row_step);

    for (c = [0 : max(0, cols - 1)]) {
        for (r = [0 : max(0, rows - 1)]) {
            translate([c * col_step, r * row_step, 0])
            cube([vent_slot_w, vent_slot_len, depth]);
        }
    }
}

// --- 120mm Fan Mount ---
// Circular fan hole + 4 corner screw holes.
// The fan sits on the outside of the panel; screws thread through into fan mount holes.
//
//   Parameters
//   size          : fan diameter in mm (default 120)
//   screw_spacing : distance between screw hole centres (default 105mm for 120mm fan)
//   screw_d       : screw hole diameter — 4mm fits M3 self-tapping or M3 clearance
//   depth         : panel thickness to cut through
//
module fan_cutout(size = 120, screw_spacing = 105, screw_d = 4, depth = wall_thickness + 0.2) {
    // Main circular opening (5mm smaller than fan for mounting flange)
    cylinder(d = size - 5, h = depth, $fn = 64);

    // Four mounting screw holes at corners of screw_spacing square
    half = screw_spacing / 2;
    for (sx = [-half, half]) {
        for (sy = [-half, half]) {
            translate([sx, sy, 0])
            cylinder(d = screw_d, h = depth, $fn = 16);
        }
    }
}

// --- QR Code Repair Surface ---
// An embossed rectangular platform on an interior wall face.
// Contains a shallow recess (qr_recess_depth mm deep) exactly qr_size × qr_size.
// Users press a printed QR sticker or a small 3D-printed QR tile into the recess.
//
// HOW TO GENERATE YOUR QR CODE
//   1. Go to a QR code generator (e.g. qr-code-generator.com)
//   2. Enter the URL for this component in boms/tier2_commons.md (or the full repair guide)
//   3. Download as PNG, resize to 28×28mm (leaving 1mm white border inside the recess)
//   4. Print on adhesive polyester label stock (e.g. Avery 6450)
//   5. Press into the recessed surface — the border holds it flush
//
// The platform is oriented so its face (XY plane) is flush with the wall's interior surface.
// The module is called with translate + rotate to position it on the correct wall.
//
module qr_surface() {
    difference() {
        // Raised platform (protrudes inward from wall)
        cube([qr_platform, qr_platform, qr_platform_h]);

        // Recessed area for QR sticker — cut from the top face
        translate([qr_border, qr_border, qr_platform_h - qr_recess_depth])
        cube([qr_size, qr_size, qr_recess_depth + 0.1]);
    }

    // ----- Optional: engraved text label below the QR surface -----
    // Uncomment the block below, set your font path, and adjust position.
    // (OpenSCAD requires a system font to render text.)
    //
    // translate([0, -6, 0])
    // linear_extrude(height = 0.8)
    // text("SCAN TO REPAIR", size = 3.5, font = "Liberation Sans:style=Bold",
    //      halign = "left");
}

// --- M3 Standoff (Motherboard) ---
// Solid cylinder representing a brass M3 standoff.
// In the real build, order "M3 × 6.5mm brass PCB standoffs" (widely available, ~$0.05 each).
// This module is used in mb_tray() for visual verification of hole positions.
module mb_standoff() {
    cylinder(d = 5, h = mb_standoff_h, $fn = 16);
}

// --- Rubber Foot Recess ---
// Shallow recess on the bottom panel for adhesive rubber feet.
// Match the diameter to whatever feet you buy (typically 15–20mm).
module rubber_foot_recess(d = 20) {
    cylinder(d = d + 1, h = 3, $fn = 32);
}


// =============================================================================
// SECTION 4 — CHASSIS PANELS
// Each panel is a separate module.
//
// TO PRINT OR CUT A SINGLE PANEL:
//   1. Scroll to Section 7 (RENDER) at the bottom of this file.
//   2. Comment out  full_chassis();
//   3. Uncomment the panel you want, e.g.  bottom_panel();
//   4. Press F6, then File > Export > Export as STL.
// =============================================================================


// --- BOTTOM PANEL ---
// Solid floor with rubber foot recesses in the four corners and
// a central cable management slot.
module bottom_panel() {
    difference() {
        cube([ext_w, ext_d, wall_thickness]);

        // Rubber foot recesses — 15mm inset from each corner
        foot_inset = 15;
        for (fx = [foot_inset, ext_w - foot_inset]) {
            for (fy = [foot_inset, ext_d - foot_inset]) {
                translate([fx, fy, wall_thickness - 3])
                rubber_foot_recess();
            }
        }

        // Central cable management slot — helps route internal cables neatly
        translate([ext_w / 2 - 20, ext_d / 2 - 40, -0.1])
        cube([40, 80, wall_thickness + 0.2]);
    }
}


// --- TOP PANEL ---
// One 120mm intake fan mount in the front-centre.
// Supplementary ventilation grid toward the rear (passive PSU ventilation).
module top_panel() {
    difference() {
        cube([ext_w, ext_d, wall_thickness]);

        // Primary 120mm intake fan — centred on width, in the forward third
        translate([ext_w / 2, ext_d * 0.33, -0.1])
        fan_cutout(size = fan_size, screw_spacing = fan_screw_spacing,
                   depth = wall_thickness + 0.2);

        // Supplementary passive ventilation — rear two-thirds of top
        translate([wall_thickness * 2, ext_d * 0.50, -0.1])
        vent_grid(
            grid_w = ext_w - wall_thickness * 4,
            grid_h = ext_d * 0.38,
            depth  = wall_thickness + 0.2
        );
    }
}


// --- FRONT PANEL ---
// Power button cutout (16mm) + optional USB-A port slot + lower intake vents for GPU.
module front_panel() {
    difference() {
        cube([ext_w, wall_thickness, ext_h]);

        // 16mm power button hole — centred horizontally, upper quarter of panel height
        translate([ext_w / 2, -0.1, ext_h * 0.75])
        rotate([-90, 0, 0])
        cylinder(d = 16 + fit_tolerance, h = wall_thickness + 0.2, $fn = 32);

        // USB-A pass-through slot (optional external USB hub / LED strip connector)
        // 34mm wide × 16mm tall cutout, centred horizontally
        translate([ext_w / 2 - 17, -0.1, ext_h * 0.58])
        cube([34, wall_thickness + 0.2, 16]);

        // Lower intake ventilation — feeds fresh air to GPU (bottom 35% of front face)
        translate([wall_thickness * 3, -0.1, wall_thickness * 2])
        vent_grid(
            grid_w = ext_w - wall_thickness * 6,
            grid_h = ext_h * 0.30,
            depth  = wall_thickness + 0.2
        );
    }
}


// --- REAR PANEL ---
// Contains:
//   · Mini-ITX I/O shield opening   (158.76 × 44.45mm, per spec)
//   · 2× PCIe bracket slots         (dual-slot GPU, 14.9mm each)
//   · PSU IEC C14 inlet cutout      (28 × 20mm)
//   · 120mm exhaust fan mount
//   · Lower passive exhaust vents
//
// I/O SHIELD POSITION NOTES:
//   The I/O opening is referenced from the motherboard's edge.
//   The MB is centred on the chassis width. The I/O opening starts
//   mb_hole_inset (6.35mm) from the left edge of the MB.
module rear_panel() {
    // Calculate MB X offset: MB is centred between left wall and PSU divider
    mb_x_in_chassis = wall_thickness + (int_w - mb_width - psu_w - wall_thickness) / 2 + psu_w + wall_thickness;
    // I/O shield starts 6.35mm from MB left edge
    io_x            = mb_x_in_chassis + mb_hole_inset;
    // I/O shield sits at the top of the MB zone (just below the top panel)
    io_z            = ext_h - wall_thickness - mb_zone_h + mb_standoff_h;

    // PCIe slot Z position: pcie_from_mb_top below the top of the MB
    pcie_z          = io_z + io_shield_h - pcie_from_mb_top + 50;
    // PCIe slots start ~14mm in from left edge of I/O shield
    pcie_x          = io_x + 14;

    // PSU IEC C14 inlet
    psu_inlet_x     = wall_thickness + 15;
    psu_inlet_z     = ext_h - wall_thickness - psu_h + 20;

    difference() {
        cube([ext_w, wall_thickness, ext_h]);

        // I/O shield opening (Mini-ITX specification)
        translate([io_x, -0.1, io_z])
        cube([io_shield_w, wall_thickness + 0.2, io_shield_h]);

        // PCIe bracket slots — 2 slots for dual-slot GPU
        // Standard PCIe bracket opening: 14.9mm wide × 120mm tall
        for (s = [0, 1]) {
            translate([pcie_x + s * (14.9 + 1.5 + fit_tolerance), -0.1, pcie_z])
            cube([14.9 + fit_tolerance, wall_thickness + 0.2, 120]);
        }

        // PSU IEC C14 inlet (receptacle mounted on PSU rear)
        translate([psu_inlet_x, -0.1, psu_inlet_z])
        cube([28 + fit_tolerance, wall_thickness + 0.2, 20 + fit_tolerance]);

        // 120mm exhaust fan — centred horizontally, upper-mid height
        translate([ext_w / 2, -0.1, ext_h * 0.62])
        rotate([-90, 0, 0])
        fan_cutout(size = fan_size, screw_spacing = fan_screw_spacing,
                   depth = wall_thickness + 0.2);

        // Lower passive exhaust vents (below fan)
        translate([wall_thickness * 3, -0.1, wall_thickness * 2])
        vent_grid(
            grid_w = ext_w - wall_thickness * 6,
            grid_h = ext_h * 0.20,
            depth  = wall_thickness + 0.2
        );
    }
}


// --- LEFT SIDE PANEL (GPU side) ---
// This is the removable access panel on the GPU side of the chassis.
// Contains large ventilation slots at GPU height for exhaust airflow.
//
// QR CODE SURFACE #1 — GPU REPAIR
//   Embossed on the interior face of this panel at GPU height.
//   Position: mid-panel depth, mid-GPU zone height.
//   Link the QR code to: boms/tier2_commons.md#t2-004-discrete-gpu-12gb-vram
module left_panel() {
    // GPU zone sits at the bottom of the chassis internally
    gpu_zone_z = wall_thickness;
    gpu_vent_z = gpu_zone_z + gpu_clearance_mm;

    // Vent field height: GPU zone height minus bottom margin
    gpu_vent_h = gpu_zone_h - gpu_clearance_mm - wall_thickness;

    difference() {
        cube([wall_thickness, ext_d, ext_h]);

        // Large ventilation array at GPU bay height
        // These slots exhaust hot air from the GPU cooler
        translate([-0.1, wall_thickness * 3, gpu_vent_z])
        rotate([0, 90, 0])
        vent_grid(
            grid_w = gpu_vent_h,
            grid_h = ext_d - wall_thickness * 6,
            depth  = wall_thickness + 0.2
        );
    }

    // QR Code Surface — GPU
    // translate: places platform on interior face (X = wall_thickness),
    //            centred in panel depth, at mid-height of GPU zone
    translate([
        wall_thickness,                             // flush with interior wall face
        ext_d / 2 - qr_platform / 2,               // centred depth
        gpu_zone_z + gpu_zone_h / 2 - qr_platform / 2  // mid GPU zone height
    ])
    qr_surface();
}


// --- RIGHT SIDE PANEL (Motherboard side) ---
// Interior face holds the motherboard tray. No ventilation holes here — the
// MB components need dust protection on this side. Airflow enters from top/front.
//
// QR CODE SURFACE #2 — PSU REPAIR
//   Embossed on the interior face at PSU height (upper rear quadrant).
//   Link the QR code to: boms/tier2_commons.md#t2-007-sfx-power-supply-650w
//
// QR CODE SURFACE #3 — SSD REPAIR
//   Embossed on the interior face at SSD bay height (lower front quadrant).
//   Link the QR code to: boms/tier2_commons.md#t2-006-sata-ssd-2tb-data
module right_panel() {
    // PSU zone: top of chassis, rear half
    psu_zone_z = ext_h - wall_thickness - psu_h - wall_thickness;

    // SSD zone: bottom of chassis, front half
    ssd_zone_z = wall_thickness * 2;

    // Solid panel — no ventilation cutouts on MB side
    cube([wall_thickness, ext_d, ext_h]);

    // QR Code Surface #2 — PSU
    // Interior face: at X = 0 (this module sits at X = ext_w - wall_thickness in assembly)
    // So QR platform must point in -X direction. We place it facing inward.
    translate([
        0,
        wall_thickness * 3,      // near rear
        psu_zone_z
    ])
    qr_surface();

    // QR Code Surface #3 — SSD
    translate([
        0,
        wall_thickness * 3,      // near front
        ssd_zone_z
    ])
    qr_surface();
}


// --- MOTHERBOARD TRAY (internal sub-panel) ---
// A flat internal plate that the Mini-ITX motherboard mounts to.
// Recommended material: 3mm aluminium sheet (laser cut) or 4mm PETG (3D printed).
//
// MOUNTING HOLE POSITIONS (Mini-ITX specification)
//   The four holes are at the corners of a 154.94 × 154.94mm square,
//   with the first hole 6.35mm from the top-left corner of the PCB.
//
//   Hole | X from tray origin | Y from tray origin
//   -----+--------------------+-------------------
//     A  |  6.35mm            |  6.35mm
//     B  |  6.35 + 154.94mm   |  6.35mm
//     C  |  6.35mm            |  6.35 + 154.94mm
//     D  |  6.35 + 154.94mm   |  6.35 + 154.94mm
//
// The tray also has a large CPU backplate cutout in the centre to allow
// access when fitting the cooler, and an I/O opening at the rear edge.
module mb_tray() {
    tray_w = mb_width  + 10;  // 10mm margin each side
    tray_d = mb_depth  + 10;
    tray_t = 2.5;             // [mm] Tray thickness

    // Standoff hole positions (Mini-ITX spec)
    hole_a = [mb_hole_inset + 5,                  mb_hole_inset + 5];
    hole_b = [mb_hole_inset + 5 + mb_hole_pattern, mb_hole_inset + 5];
    hole_c = [mb_hole_inset + 5,                  mb_hole_inset + 5 + mb_hole_pattern];
    hole_d = [mb_hole_inset + 5 + mb_hole_pattern, mb_hole_inset + 5 + mb_hole_pattern];
    standoff_positions = [hole_a, hole_b, hole_c, hole_d];

    difference() {
        cube([tray_w, tray_d, tray_t]);

        // CPU backplate cutout: 90×90mm centred on the CPU socket region
        // Mini-ITX CPU socket centre is approximately at (85, 85) from board origin
        translate([tray_w / 2 - 45, tray_d / 2 - 45, -0.1])
        cube([90, 90, tray_t + 0.2]);

        // I/O opening slot at the rear edge of the tray (aligns with rear panel)
        translate([mb_hole_inset + 5, tray_d - 5, -0.1])
        cube([io_shield_w, 6, tray_t + 0.2]);
    }

    // Place standoffs at the four Mini-ITX hole positions
    for (pos = standoff_positions) {
        translate([pos[0], pos[1], tray_t])
        mb_standoff();
    }
}


// =============================================================================
// SECTION 5 — FULL CHASSIS ASSEMBLY
// Assembles all panels at their correct positions.
// =============================================================================

module full_chassis() {
    // Bottom panel — at Z = 0
    bottom_panel();

    // Top panel — at Z = ext_h - wall_thickness
    translate([0, 0, ext_h - wall_thickness])
    top_panel();

    // Front panel — at Y = 0
    front_panel();

    // Rear panel — at Y = ext_d - wall_thickness
    translate([0, ext_d - wall_thickness, 0])
    rear_panel();

    // Left side panel (GPU side) — at X = 0
    left_panel();

    // Right side panel (MB side) — at X = ext_w - wall_thickness
    translate([ext_w - wall_thickness, 0, 0])
    right_panel();

    // Motherboard tray — internal sub-panel, mounted to right panel interior
    // Positioned: left of right wall, centred in chassis depth, at MB zone height
    translate([
        ext_w - wall_thickness * 2 - (mb_width + 10),
        wall_thickness + (int_d - (mb_depth + 10)) / 2,
        ext_h - wall_thickness - mb_zone_h
    ])
    mb_tray();
}


// =============================================================================
// SECTION 6 — COMPONENT GHOST VISUALISATION
// Renders translucent boxes representing the actual components to verify clearances.
// These are NOT part of the chassis — they are for checking fit only.
//
// To activate: uncomment component_ghosts() in Section 7.
// =============================================================================

module component_ghosts() {
    // Motherboard (blue)
    color("dodgerblue", 0.25)
    translate([
        ext_w - wall_thickness - (mb_width + 10) + 5,
        wall_thickness + (int_d - mb_depth) / 2,
        ext_h - wall_thickness - mb_zone_h + mb_standoff_h + mb_pcb_t
    ])
    cube([mb_width, mb_depth, mb_pcb_t + cpu_cooler_max_h]);

    // GPU (red) — dual-slot, runs from rear toward front along Y axis
    color("tomato", 0.25)
    translate([
        ext_w / 2 - gpu_slot_width / 2,
        wall_thickness,
        wall_thickness + gpu_clearance_mm
    ])
    cube([gpu_slot_width, gpu_length, gpu_height]);

    // PSU (grey) — top-rear of chassis
    color("slategrey", 0.25)
    translate([
        wall_thickness * 2,
        ext_d - wall_thickness - psu_d,
        ext_h - wall_thickness - psu_h
    ])
    cube([psu_w, psu_d, psu_h]);

    // SSD bays (green) — stacked, front-bottom
    color("limegreen", 0.25)
    for (i = [0 : ssd_bay_count - 1]) {
        translate([
            ext_w / 2 - ssd_w / 2,
            wall_thickness * 2,
            wall_thickness * 2 + i * (ssd_h + ssd_bay_gap)
        ])
        cube([ssd_w, ssd_d, ssd_h]);
    }
}


// =============================================================================
// SECTION 7 — RENDER
//
// FULL CHASSIS: Press F5 to preview, F6 to render.
//
// SINGLE PANEL EXPORT (for printing or laser cutting):
//   1. Comment out  full_chassis();
//   2. Uncomment one panel below
//   3. F6 → File > Export > Export as STL
//
// COMPONENT CLEARANCE CHECK:
//   Uncomment  component_ghosts();  to overlay transparent component boxes.
// =============================================================================

full_chassis();

// component_ghosts();     // <-- uncomment to check component clearances

// Individual panel exports (uncomment one at a time):
// bottom_panel();
// top_panel();
// front_panel();
// rear_panel();
// left_panel();
// right_panel();
// mb_tray();
// qr_surface();           // standalone QR holder — see also qr_surface_v1.scad
