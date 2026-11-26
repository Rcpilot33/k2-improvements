# Slicer templates for the K2 Plus and K2 Pro

For **Machine start G-code**, choose your printer and slicer first.
Use the [K2 Plus templates](#k2-plus), [K2 Pro Creality Print templates](#k2-pro-creality-print),
or [K2 Pro OrcaSlicer templates](#k2-pro-orcaslicer).

OrcaSlicer has separate preset fields for [filament changes and temperatures](#orcaslicer-filament-changes-k2-plus-and-k2-pro-04-mm)
and [layer reporting in Fluidd](#orcaslicer-layer-reporting-in-fluidd).

## OrcaSlicer layer reporting in Fluidd

On the K2 Plus and K2 Pro, Orca can report the layer being printed to Fluidd
even while the nozzle lifts for travel or a filament change. This works with
or without KAMP. Append the [layer-change template](./orca-layer-change.gcode)
to **Printer preset → Machine G-code → Layer change G-code**
(`layer_change_gcode`, the **after** layer-change field).

Save the preset. For an existing 3MF, reselect the updated printer preset and
reslice. In a 60-layer export, the first layer should contain
`SET_PRINT_STATS_INFO CURRENT_LAYER=1 TOTAL_LAYER=60` and the last should
report `CURRENT_LAYER=60 TOTAL_LAYER=60`.

## OrcaSlicer filament changes (K2 Plus and K2 Pro, 0.4 mm)

In your **printer preset → Machine G-code → Change filament G-code**, use
the template for your model. Both guard the travel moves with
`{if layer_num >= 0}`. The Plus parks at Y245. The Pro parks at Y160 and
includes extra Z clearance when printing by object.
Both templates end at the park position with the spiral lift still in effect.
Orca's subsequent print moves handle the return to printing height.

- [K2 Plus change filament G-code](./k2-plus/orca-change-filament.gcode)
- [K2 Pro change filament G-code](./k2-pro/orca-change-filament.gcode)

If a CFS tool change leaves the nozzle at its flush temperature, add the
[temperature snippet](./orca-filament-start-temperature.gcode) to **Filament
start G-code** in each participating filament preset. Preserve any other
filament initialization you use. The snippet issues `M104` with the filament's
first-layer or regular nozzle target. It applies with either purge method.

An existing 3MF can carry older copies of these settings. After updating the
presets, reslice and check the exported G-code. For example, when changing to
black PETG configured for 240 °C, look for `M104 S240` **after** the incoming
tool command and before printing resumes.

## K2 Pro Creality Print

Copy one complete file into **Machine start G-code** in a K2 Pro 0.4 mm user preset. All four pass the bed, nozzle and chamber temperatures and the quoted filament type to `START_PRINT`.

| Template | Plate selection | Purge before the first layer |
|---|---|---|
| [Material only](./k2-pro/creality-start-material-only.gcode) | Uses the configured default | Front-left corner |
| [Material + surface profiles](./k2-pro/creality-start-material-surface-profiles.gcode) | Passes the selected plate | Front-left corner |
| [Material + KAMP](./k2-pro/creality-start-material-kamp.gcode) | Uses the configured default | `LINE_PURGE` |
| [Material + surface profiles + KAMP](./k2-pro/creality-start-material-surface-profiles-kamp.gcode) | Passes the selected plate | `LINE_PURGE` |

Creality Print evaluates `multicolor_method` when slicing. With **Calculation of flush amount slice** enabled, each template includes the Pro's rear-chute load, flush and wipe sequence from the 7.3 system preset. With it disabled, the template selects the initial tool directly. Both paths then use the purge listed above. The KAMP variants require an installed `LINE_PURGE` macro and let it choose the purge location. For stock-probe RC3 testing without KAMP or plate selection, start with **Material only**.

Creality Print 7.3 exported all four variants with the flush setting both enabled and disabled. A native 7.1 export and physical Pro runs with these templates still need confirmation.

## K2 Pro OrcaSlicer

Choose one file for the K2 Pro printer preset's **Machine start G-code**. All four use the supplied single-tool sequence, wait for the initial nozzle temperature with `M109`, and lift to Z3 before purging.

| Template | Plate selection | Purge |
|---|---|---|
| [Material only](./k2-pro/orca-start-material-only.gcode) | Default | Stock front-left lines |
| [Material + surface profiles](./k2-pro/orca-start-material-surface-profiles.gcode) | Selected Orca plate | Stock front-left lines |
| [Material + KAMP](./k2-pro/orca-start-material-kamp.gcode) | Default | `LINE_PURGE` |
| [Material + surface profiles + KAMP](./k2-pro/orca-start-material-surface-profiles-kamp.gcode) | Selected Orca plate | `LINE_PURGE` |

The stock purge extrudes 15 mm on each leg at F6000. For KAMP, enable object labels in Orca and install the printer's KAMP adaptive purge extra.

All four Pro Orca templates were sliced with OrcaSlicer 2.5.0 using a K2 Pro profile and a PLA test cube. The exports confirmed the purge commands and Textured PEI selection. Physical print testing of these Orca templates is pending.

## K2 Plus

The files in [k2-plus](./k2-plus/) replace the complete machine-start G-code block in a K2 Plus
slicer profile. Each slicer has four variants so material-based Z offsets,
plate selection, and KAMP can be enabled independently or together. Keep
Creality's system preset unchanged as a fallback.

| File | Material | Plate selection | KAMP purge | Status |
|---|---|---|---|---|
| [creality-start-material-only.gcode](./k2-plus/creality-start-material-only.gcode) | Yes | No; loads `default` | No | PASS — Creality Print 7.1.1 |
| [creality-start-material-surface-profiles.gcode](./k2-plus/creality-start-material-surface-profiles.gcode) | Yes | Yes | No | PASS — Creality Print 7.1.1 |
| [creality-start-material-kamp.gcode](./k2-plus/creality-start-material-kamp.gcode) | Yes | No; loads `default` | Yes | PASS — Creality Print 7.1.1 |
| [creality-start-material-surface-profiles-kamp.gcode](./k2-plus/creality-start-material-surface-profiles-kamp.gcode) | Yes | Yes | Yes | PASS — Creality Print 7.1.1 |
| [orca-start-material-only.gcode](./k2-plus/orca-start-material-only.gcode) | Yes | No | No | Orca 2.4.2 standard workflow tested |
| [orca-start-material-kamp.gcode](./k2-plus/orca-start-material-kamp.gcode) | Yes | No | Yes | KAMP and enabled stock fallback tested |
| [orca-start-material-surface-profiles.gcode](./k2-plus/orca-start-material-surface-profiles.gcode) | Yes | Yes | No | Exported plate names verified; full matrix pending |
| [orca-start-material-surface-profiles-kamp.gcode](./k2-plus/orca-start-material-surface-profiles-kamp.gcode) | Yes | Yes | Yes | `high_temp` workflow tested; full matrix pending |

The plate-selection variants pass `SURFACE=` to either the Cartographer plate
workflow or the optional stock-PR-Touch plate-aware mesh feature. On a
Cartographer setup it selects matching scan and touch models. On a stock-probe
setup it becomes part of the saved mesh profile name. The material-only and
KAMP-only variants intentionally omit `SURFACE=`; Cartographer then loads its
`default` models, while the stock-probe path retains its original
temperature-only mesh name. All eight variants pass `MATERIAL=` so
`START_PRINT` can apply the matching offset from `_START_PRINT_VARS`.
All branches quote the material value as `MATERIAL="{filament_type[initial_tool]}"`.
Keep these quotes: a custom type such as `PLA+ 2.0` otherwise becomes two command
arguments and fails before `START_PRINT` can run. Quoting also works for
single-word types such as `PLA` and `PETG` in both slicers.

The four Creality Print variants were validated on printer firmware `1.1.5.5`.

## Use

1. For either KAMP variant in Creality Print 7.x, enable **Exclude objects**
   under Process settings -> Others. **Label objects** alone is insufficient.
   In OrcaSlicer, enable **Label objects** or **Use exclude_object**.
2. Open the printer profile's **Machine start G-code** setting.
3. Replace the complete block with the desired template.
4. Save the profile and slice a test object.
5. Confirm the generated `START_PRINT` line contains the expected
   quoted `MATERIAL=` value (for example, `MATERIAL="PLA+ 2.0"`). Re-slice after
   updating an existing preset; previously exported G-code is not changed.
6. For a KAMP variant, confirm the output contains `EXCLUDE_OBJECT_DEFINE`,
   `M109`, and `LINE_PURGE` before printing.
7. For a plate-selection variant, confirm the output contains the expected
   `SURFACE=` value before printing.

See the parent [KAMP guide](../README.md) for installation, verification,
tuning, and troubleshooting.

## Orca plate support

The six exported plate values and their models are listed in the
[plate mapping](../../cartographer-macros/README.md#slicer-choice-and-orca-mapping).
Cartographer and no-Carto use the same `SURFACE` strings. Install the
Cartographer plate workflow or the stock PR Touch **Plate-aware mesh** extra.
For example, `orca_cool_plate` at 70/0 degrees resolves to stock mesh
`orca_cool_plate_70.0c_0.0c`. Existing CP profile names are unchanged.

The Orca templates retain the user's stock single-tool start sequence; they
do not import Creality-only `multicolor_method` logic or add CFS support.
Save separate Standard, KAMP, Plate, and Plate + KAMP user presets. Repository
updates do not edit slicer presets; copy the chosen template manually.

Without exclude-object geometry, adaptive meshing cannot be used.
`LINE_PURGE` uses the stock-style fallback only when that setting is enabled;
otherwise it skips purging. Do not append the stock purge tail to a KAMP template.
The expanded UI and full stock-probe/plate matrix still need printer testing.
