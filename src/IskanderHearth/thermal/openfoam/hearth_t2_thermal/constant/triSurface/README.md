# chassis_interior.stl — Generation Procedure

This directory contains the STL surface mesh that defines the interior
geometry of the Iskander Hearth Tier 2 chassis for snappyHexMesh.

**The STL file is NOT committed to the repository** because it is a binary
build artefact generated from the OpenSCAD source files. Regenerate it
when the chassis geometry changes.

---

## How to generate chassis_interior.stl

### Step 1 — Export chassis interior from OpenSCAD

Open `enclosures/hearth_chassis_v2.scad` in OpenSCAD 2024.x.

The STL must include **named regions** matching the patch names in
`system/snappyHexMeshDict`. Use the following export procedure:

```openscad
// Add this to the bottom of hearth_chassis_v2.scad for STL export,
// then export each surface as a separate STL and merge with FreeCAD or Blender.
//
// Required named surface groups:
//   chassis_walls   — all interior wall faces
//   gpu_surface     — GPU heatsink footprint (approx 200×111mm rectangle at GPU Z position)
//   cpu_surface     — CPU cooler contact area (approx 120×120mm at MB Z position)
//   intake_fan      — circular fan aperture on top panel (d=115mm)
//   exhaust_fan     — circular fan aperture on rear panel (d=115mm)
//   gpu_vent_slots  — left panel vent slot array
//   front_vents     — front panel lower vent slot array
```

### Step 2 — Export with correct orientation

File → Export → Export as STL (ASCII, not binary — easier to verify).
Scale: 1mm in OpenSCAD = 0.001m in OpenFOAM.
After export, scale: `surfaceTransformPoints -scale "(0.001 0.001 0.001)" chassis_interior.stl chassis_interior_m.stl`

### Step 3 — Extract surface features

```bash
cd thermal/openfoam/hearth_t2_thermal
surfaceFeatureExtract
```

This reads `system/surfaceFeatureDictionary` and produces `constant/triSurface/chassis_interior.eMesh`.

### Step 4 — Verify STL watertight

```bash
surfaceCheck constant/triSurface/chassis_interior.stl
# Must report: closed surface, no non-manifold edges
```

---

## Simplified geometry option (for initial validation)

If the full chassis STL is not yet available, substitute with a simple
box representing the interior air volume. The blockMeshDict already
defines this box — you can run `buoyantSimpleFoam` on the block mesh
alone with the GPU/CPU heat sources applied as patches on the block faces.
This gives a rough temperature estimate (±15°C) before the full snappy mesh.
