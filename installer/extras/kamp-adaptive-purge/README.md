# KAMP Adaptive Purge

Replaces the fixed front-left purge line with a purge positioned near the
current print and inside the usable bed area.

This is useful when Cartographer mount offsets move `mesh_min` away from the
front or left edge. A fixed purge outside that mesh can drag the nozzle across
an uncorrected part of the bed.

## Requirements

KAMP needs all three of the following:

1. Slicer-generated `EXCLUDE_OBJECT_DEFINE` polygons. Depending on the slicer,
   these come from **Label objects**, **Exclude objects**, or
   **Use exclude_object**.
2. `LINE_PURGE` in the machine-start G-code instead of the fixed purge moves.
3. A blocking `M109` before `LINE_PURGE` so the nozzle reaches printing
   temperature first.

Without those polygons, KAMP cannot determine the print boundary. By default,
the K2 boundary guard prints a warning and safely skips the purge. Users may
explicitly enable the preserved stock-style purge fallback described below.

## Install

Use **Extras -> KAMP adaptive purge**. The installer adds:

- the KAMP repository under `/mnt/UDISK/root`;
- a validated K2-compatible regular-file copy of upstream `Line_Purge.cfg`
  (intentionally not a symlink);
- K2-specific settings;
- automatic prime-tower footprint detection;
- `[exclude_object]` when it is not already configured; and
- optional firmware retraction when selected.

During an interactive install, the installer displays the K2 Plus KAMP
settings and lets you keep or change them. User selections are written to the
later-loaded `custom/overrides.cfg`; reinstalling or updating KAMP refreshes
the maintained defaults without replacing those selections. Reopen
**Optional Extras -> KAMP adaptive purge -> Review/change settings** to adjust
them later without reinstalling KAMP.

It intentionally does not install KAMP Smart Park or Adaptive Meshing. The
project's `START_PRINT` and Cartographer flow already provide those functions.

The installed `Line_Purge.cfg` makes three compatibility corrections to the
upstream macro:

1. `G10` and `G11` are quoted when stored as Jinja strings for firmware
   retraction.
2. KAMP restores its own final retract after the short string-breaking move.
   The slicer can then perform its normal retract, travel to the object, and
   unretract immediately before the first extrusion without carrying an extra
   KAMP retraction into the first wall.
3. The purge line and its additional 10 mm string-breaking move are kept
   inside the intersection of the configured machine envelope and the active
   bed mesh. The macro tries the front, left, rear, and right sides of the
   print in that order. It warns and skips the adaptive purge if object
   geometry is missing, settings are invalid, axes are not homed, or no safe
   corridor exists.
4. When Creality Print includes a prime tower, its actual extrusion footprint
   is added to the occupied print boundary before the purge location is
   selected. This keeps KAMP from choosing a line through the tower. A tower
   alone does not substitute for missing object labels; the normal
   missing-geometry skip or stock-purge fallback still applies.

Creality Print's **Prime tower -> No sparse layers (beta)** option is not
supported on the K2 Plus. It can delay the tower until a color change, then
command the bed back to first-layer height while a tall model is already on
it, potentially driving the model into the toolhead or X rail. When an actual
prime-tower toolpath and that setting are both present, the printer-side
`START_PRINT` preflight rejects the file before printer preparation with
instructions to disable the option and reslice. Merely retaining the setting
in a profile does not block a file that contains no prime tower. KAMP also
checks again before purge as defense in depth.

The console reports when the selected G-code is being scanned. While that
scan runs, the printer holds the nozzle at 140 C and the bed (and chamber,
when requested) at the sliced `START_PRINT` preheat targets. A safety
rejection turns the heaters off and retains Klipper's failed-print state so
Creality Print and configured notifications clearly report the failure.

The same printer-side footprint is consumed by Cartographer adaptive meshing
when Cartographer is installed. No slicer variable or extra setup choice is
required beyond the normal object polygons already required by KAMP.

## Optional stock-purge fallback

`variable_stock_purge_fallback` controls what happens only when the slicer
provides no `EXCLUDE_OBJECT_DEFINE` geometry:

- `0` (default): warn and skip the purge;
- `1`: warn and run the original front-left, L-shaped stock-style purge at a
  conservative fixed speed.

The installer exposes this as **Stock purge if object data is missing (0/1)**
under **Review/change settings** and preserves it in `custom/overrides.cfg`.
The fallback cannot know where an unlabeled print is located and its X0/Y0
path may be outside an active mesh, so every use prints an explicit warning.
It is never used for a known full-bed/no-safe-corridor condition, invalid
settings, unhomed axes, or a path outside the configured machine limits.

The upstream checkout remains unchanged and can still fast-forward normally.
The installer intentionally copies and patches `Line_Purge.cfg` into
`custom/`; it does not symlink the live macro back to the upstream checkout.
This preserves the tested K2-specific `UNRETRACT` handoff while allowing the
upstream repository to update independently. If the upstream macro structure
changes, installation stops instead of silently installing an unverified
patch.

## Slicer setup

For Creality Print, choose the template matching the features enabled in that
printer profile. Keep the slicer's system preset unchanged as a fallback.

| Template | Material | Plate selection | KAMP purge |
|---|---|---|---|
| [`creality-start-material-only.gcode`](./slicer-templates/creality-start-material-only.gcode) | Yes | No; uses `default` | No |
| [`creality-start-material-surface-profiles.gcode`](./slicer-templates/creality-start-material-surface-profiles.gcode) | Yes | Yes | No |
| [`creality-start-material-kamp.gcode`](./slicer-templates/creality-start-material-kamp.gcode) | Yes | No; uses `default` | Yes |
| [`creality-start-material-surface-profiles-kamp.gcode`](./slicer-templates/creality-start-material-surface-profiles-kamp.gcode) | Yes | Yes | Yes |
| [`orca-machine-start.gcode`](./slicer-templates/orca-machine-start.gcode) | Yes | Yes | Yes |

All four Creality Print variants passed printer testing on firmware `1.1.5.5`.
The Orca template remains dependent on the exact plate-name values emitted by
the user's Orca profile and is not included in that Creality Print validation.

In the slicer:

1. If using a KAMP template, enable **Label objects** or
   **Use exclude_object**.
2. Open the printer profile's **Machine start G-code** setting.
3. Replace the complete block with the appropriate supplied template.
4. Save the printer profile and slice a test object.

The material-only and KAMP-only templates omit `SURFACE=`, causing the
Cartographer wrapper to load `default` on each print or the optional stock
PR Touch plate-aware workflow to retain its temperature-only mesh name. See the
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

To verify that the installed macro is the K2-compatible patched copy:

```sh
grep -nE "set (RETRACT|UNRETRACT)|balance LINE_PURGE|boundary safety" \
  /mnt/UDISK/printer_data/config/custom/Line_Purge.cfg
```

The output should show quoted `G10`/`G11` firmware-retraction strings when that
mode is enabled, the balancing `UNRETRACT` handoff lines, and the boundary
safety decisions.

## Tuning

Use **Optional Extras -> KAMP adaptive purge -> Review/change settings**.
Maintained defaults remain in `custom/kamp_settings.cfg`; effective user
selections are stored in `custom/overrides.cfg` so they survive reinstalls.

| Variable | Default | Purpose |
|---|---:|---|
| `variable_verbose_enable` | `True` | Print purge decisions in the console |
| `variable_stock_purge_fallback` | `0` | Use stock-style purge only when object geometry is missing |
| `variable_purge_height` | `0.4` | Purge Z height |
| `variable_tip_distance` | `0` | Filament-tip distance before purging |
| `variable_purge_margin` | `10` | Distance from the print boundary |
| `variable_purge_amount` | `25` | Filament length purged |
| `variable_flow_rate` | `12` | Purge flow in mm3/s |

The boundary guard includes the complete purge and string-break path when
choosing a location. A full-bed print, an excessively large purge amount, or a
large margin can leave no valid corridor; in that case it warns and skips the
adaptive purge instead of commanding an out-of-bounds move.

## Activation

The installer does not restart Klipper so it cannot interrupt an active print.
When no print is active, run `FIRMWARE_RESTART` and wait for the complete K2
startup sequence before the next `G28`. If the restart fails, power-cycle the
printer before homing.

## Credit

KAMP is maintained by Kyle Isom in
[Klipper-Adaptive-Meshing-Purging](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging).
This repository provides the K2 Plus installer, settings, and slicer templates.
