# Enclosures

OpenSCAD parametric chassis designs for Iskander Hearth nodes.

## Files

| File | Description |
|---|---|
| [`hearth_chassis_v1.scad`](./hearth_chassis_v1.scad) | Full Tier 2 Commons Node chassis — all 6 panels + MB tray |
| [`qr_surface_v1.scad`](./qr_surface_v1.scad) | Standalone printable QR repair tile for use in any chassis |

---

## Requirements

- **OpenSCAD** (free): https://openscad.org/downloads.html
- Version 2021.01 or later recommended

---

## What the Chassis Fits

| Component | Spec | Notes |
|---|---|---|
| Motherboard | Mini-ITX, 170 × 170mm | All Mini-ITX boards |
| PSU | SFX (125 × 100 × 63.5mm) | Change `psu_w/d/h` for ATX |
| GPU | Up to 240mm long, dual-slot | Adjust `gpu_length` for shorter cards |
| CPU Cooler | Up to 58mm tall | Noctua NH-L9a-AM5 = 37mm |
| Drive Bays | 2× 2.5-inch SSD | Adjust `ssd_bay_count` for more |
| Fan Mounts | 2× 120mm | Top intake + rear exhaust |

---

## Manufacturing Options

### Option A — 3D Printing (Recommended for Prototypes)

Print each panel separately.

**Recommended settings:**

| Setting | Value |
|---|---|
| Material | PETG (heat resistant) or ASA (UV stable for outdoor use) |
| Layer height | 0.2mm |
| Perimeters / walls | 3 (minimum) |
| Infill | 40% Gyroid or Honeycomb |
| Supports | None needed — panels are flat |
| Bed temperature | PETG: 70°C / ASA: 90°C |

**Print order (largest to smallest to minimise thermal cycling on bed):**

1. `bottom_panel()` → export STL
2. `top_panel()`
3. `front_panel()`
4. `rear_panel()`
5. `left_panel()`
6. `right_panel()`
7. `mb_tray()`

**How to export a single panel:**
1. Open `hearth_chassis_v1.scad` in OpenSCAD
2. In Section 7 (bottom of file), comment out `full_chassis();`
3. Uncomment the panel you want, e.g. `bottom_panel();`
4. Press F6 to render → File > Export > Export as STL

### Option B — Laser Cutting (Recommended for Production Runs)

Use 3mm birch plywood or 3mm acrylic sheet.

**How to export a panel as DXF:**

```openscad
// Add this to Section 7 temporarily:
projection(cut = true)
translate([0, 0, -wall_thickness / 2])
bottom_panel();  // or whichever panel
```

Then File > Export > Export as DXF. Import into LightBurn, RDWorks, or Inkscape.

**Laser settings (3mm birch plywood, typical):**

| Operation | Speed | Power |
|---|---|---|
| Cut | 10 mm/s | 80% |
| Engrave (QR surface) | 200 mm/s | 30% |

Adjust for your specific laser wattage.

### Option C — CNC Router

Export DXF as above. 3mm end mill recommended. 3mm aluminium sheet for MB tray is ideal.

---

## Assembly

Once all panels are fabricated:

1. Insert M3 brass standoffs into MB tray holes (hand-tight with needle-nose pliers)
2. Fit MB tray to right-side panel with M3 screws
3. Join panels using M3 × 10mm bolts through the wall flanges
4. The `left_panel()` is the access panel — mount last with thumbscrews for tool-free removal

---

## QR Code Repair Surfaces

Three QR surfaces are integrated into `hearth_chassis_v1.scad`:

| Surface | Location | Component |
|---|---|---|
| `left_panel()` | Interior, mid-height | GPU (T2-004) |
| `right_panel()` top | Interior, upper-rear | PSU (T2-007) |
| `right_panel()` bottom | Interior, lower-front | SSD (T2-006) |

For commercial chassis builds (not custom), print `qr_surface_v1.scad` tiles (3 per node)
and mount with 3M double-sided foam tape inside the case near each component.

**Generating QR codes:**

1. Go to any QR code generator
2. Enter the URL for the component's section in `boms/tier2_commons.md`
   (or the full GitHub URL once hosted, e.g. `github.com/iskander-os/iskander-hearth/blob/main/boms/tier2_commons.md#gpu`)
3. Download as PNG, resize to 28 × 28mm
4. Print on adhesive polyester label stock (e.g. Avery 6450)
5. Press into the 30 × 30mm recessed surface — 1mm white border provides alignment tolerance

---

## Chassis Dimensions (defaults)

These are computed from the default parameters. They will change if you edit Section 1 of the `.scad` file.

| Dimension | Value |
|---|---|
| External width | ~342mm |
| External depth | ~282mm |
| External height | ~262mm |
| Internal width | ~336mm |
| Internal GPU clearance | 12mm (below cooler fins) |
| Internal MB zone height | ~66mm |
| CPU cooler max height | 58mm |

---

## Future Enclosure Files (Planned)

| File | Description | Status |
|---|---|---|
| `hearth_chassis_v2.scad` | Revised chassis incorporating community feedback | Planned |
| `tier1_seed_enclosure.scad` | Snap-fit 3D-printed enclosure for N100 Mini PC | Planned |
| `tier3_2u_rack_panel.scad` | 2U rackmount front bezel with QR surfaces | Planned |
| `sensor_hat_bracket.scad` | INA219/INA3221 sensor board mounting bracket | Planned |
