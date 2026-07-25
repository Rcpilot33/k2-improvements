# KAMP Adaptive Purge

Replaces the fixed front-left purge line with a purge positioned near the
current print and inside the usable bed area.

This is useful when Cartographer mount offsets move `mesh_min` away from the
front or left edge. A fixed purge outside that mesh can drag the nozzle across
an uncorrected part of the bed.

## Requirements

KAMP needs all three of the following:

1. **Label objects** enabled in the slicer.
2. `LINE_PURGE` in the machine-start G-code instead of the fixed purge moves.
3. A blocking `M109` before `LINE_PURGE` so the nozzle reaches printing
   temperature first.

Without object labels, KAMP cannot determine the print boundary and may fall
back to an unsuitable purge position.

## Install

Use **Extras -> KAMP adaptive purge**. The installer adds:

- the KAMP repository under `/mnt/UDISK/root`;
- `Line_Purge.cfg` and K2-specific settings;
- `[exclude_object]` when it is not already configured; and
- optional firmware retraction when selected.

It intentionally does not install KAMP Smart Park or Adaptive Meshing. The
project's `START_PRINT` and Cartographer flow already provide those functions.

## Slicer setup

For Creality Print, choose the template matching the features enabled in that
printer profile. Keep the slicer's system preset unchanged as a fallback.

| Template | Material | Plate selection | KAMP purge |
|---|---|---|---|
| [`creality-print-material-machine-start.gcode`](./slicer-templates/creality-print-material-machine-start.gcode) | Yes | No; uses `default` | No |
| [`creality-print-plate-selection-machine-start.gcode`](./slicer-templates/creality-print-plate-selection-machine-start.gcode) | Yes | Yes | No |
| [`creality-print-kamp-machine-start.gcode`](./slicer-templates/creality-print-kamp-machine-start.gcode) | Yes | No; uses `default` | Yes |
| [`creality-print-kamp-and-plate-selection-machine-start.gcode`](./slicer-templates/creality-print-kamp-and-plate-selection-machine-start.gcode) | Yes | Yes | Yes |
| [`orca-machine-start.gcode`](./slicer-templates/orca-machine-start.gcode) | Yes | Yes | Yes |

In the slicer:

1. If using a KAMP template, enable **Label objects** or
   **Use exclude_object**.
2. Open the printer profile's **Machine start G-code** setting.
3. Replace the complete block with the appropriate supplied template.
4. Save the printer profile and slice a test object.

The material-only and KAMP-only templates omit `SURFACE=`, causing the
Cartographer wrapper to load `default` on each print. See the
[template notes](./slicer-templates/README.md) for details and verification.

## Verify before printing

Inspect the sliced G-code and confirm it contains:

- one or more `EXCLUDE_OBJECT_DEFINE` lines; and
- `LINE_PURGE` after an `M109` temperature wait.

From a shell, this command can help:

```sh
grep -E "EXCLUDE_OBJECT_DEFINE|M109|LINE_PURGE" sliced.gcode
```

If `EXCLUDE_OBJECT_DEFINE` is missing, object labels are not active. If
`LINE_PURGE` is missing, the wrong printer profile or start-G-code block was
used.

## Tuning

Edit `custom/kamp_settings.cfg`, or override values in
`custom/overrides.cfg` so local changes survive reinstalls.

| Variable | Default | Purpose |
|---|---:|---|
| `variable_purge_height` | `0.4` | Purge Z height |
| `variable_purge_margin` | `10` | Distance from the print boundary |
| `variable_purge_amount` | `25` | Filament length purged |
| `variable_flow_rate` | `12` | Purge flow in mm3/s |

Prints placed very near the front of the bed can still put the purge close to
the mesh boundary. Center the print or increase the purge margin if needed.

## Activation

The installer does not restart Klipper. Reload the configuration when ready,
then power-cycle the printer before the next `G28`.

## Credit

KAMP is maintained by Kyle Isom in
[Klipper-Adaptive-Meshing-Purging](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging).
This repository provides the K2 Plus installer, settings, and slicer templates.
