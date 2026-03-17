// =============================================================================
// ISKANDER HEARTH — Standalone QR Code Repair Surface v1
// File: qr_surface_v1.scad
// =============================================================================
// License : CERN Open Hardware Licence v2 – Strongly Reciprocal (CERN-OHL-S)
//           https://ohwr.org/cern_ohl_s_v2.txt
//
// WHAT THIS FILE IS
//   A printable QR code holder tile that can be adhesive-mounted to the
//   interior of ANY chassis (commercial Mini-ITX cases, Tier 1 Mini PCs, etc.)
//   when a custom Iskander Hearth chassis has not been built yet.
//
//   Inspired by Framework Laptop's internal repair QR system.
//
// HOW TO USE
//   1. Print this tile in PLA or PETG (no supports needed).
//   2. Generate a QR code linking to the component's repair guide.
//      Recommended size: 26×26mm (fits within the 28×28mm recess with margin).
//   3. Print on adhesive polyester label stock and trim to 28×28mm.
//   4. Press the label into the recessed area — the 2mm border holds it flush.
//   5. Apply 3M double-sided foam tape to the flat back of the tile.
//   6. Mount inside your chassis wall next to the relevant component.
//
// THREE TILES ARE NEEDED PER TIER 2 BUILD
//   - GPU bay tile   → links to boms/tier2_commons.md (component T2-004)
//   - PSU bay tile   → links to boms/tier2_commons.md (component T2-007)
//   - SSD bay tile   → links to boms/tier2_commons.md (component T2-006)
// =============================================================================

// =============================================================================
// PARAMETERS — modify here
// =============================================================================

qr_size          = 30;   // [mm]  Square area for the QR sticker. 30mm = Framework standard.
                         //       <-- CHANGE ME if your sticker is a different size

qr_recess_depth  = 0.8;  // [mm]  How deep the sticker sits into the recess.
                         //       Increase if your label stock is thick.

qr_border        = 2;    // [mm]  Raised border width around the recess.
                         //       2mm provides enough structure for the sticker edge.

tile_thickness   = 2.0;  // [mm]  Total tile thickness including platform.
                         //       2mm is printable and rigid enough.

mount_tab_w      = 8;    // [mm]  Width of the mounting tab on each of the two sides.
mount_tab_h      = 5;    // [mm]  Height of mounting tab (protrudes below the tile base).
                         //       The tabs act as guides when pressing the tile against a wall.

// =============================================================================
// DERIVED DIMENSIONS
// =============================================================================

total_w = qr_size + qr_border * 2;    // = 30 + 4 = 34mm (outer width of tile)
total_d = qr_size + qr_border * 2;    // = 34mm (outer depth)
platform_raise = 2.0;                  // [mm]  How far the QR platform sits above the base

// =============================================================================
// QR SURFACE TILE MODULE
// =============================================================================

module qr_tile() {
    union() {
        // Base plate — the flat back that adheres to the chassis wall
        cube([total_w, total_d, tile_thickness]);

        // Raised platform — sits on top of base plate, recessed for sticker
        translate([0, 0, tile_thickness])
        difference() {
            // Platform solid
            cube([total_w, total_d, platform_raise]);

            // Sticker recess — sunken area for QR label
            // Recess is exactly qr_size × qr_size, qr_recess_depth deep
            translate([qr_border, qr_border, platform_raise - qr_recess_depth])
            cube([qr_size, qr_size, qr_recess_depth + 0.1]);
        }

        // Left mounting tab
        translate([-mount_tab_w, total_d / 2 - 4, 0])
        cube([mount_tab_w, 8, tile_thickness]);

        // Right mounting tab
        translate([total_w, total_d / 2 - 4, 0])
        cube([mount_tab_w, 8, tile_thickness]);
    }
}

// =============================================================================
// RENDER
// Press F6, then File > Export > Export as STL.
// Print 3 copies per Tier 2 node: GPU / PSU / SSD bay.
// =============================================================================

qr_tile();
