# KAMP Slicer Templates

These files replace the complete machine-start G-code block in a K2 Plus
slicer profile. Each slicer has four variants so material-based Z offsets,
plate selection, and KAMP can be enabled independently or together. Keep
Creality's system preset unchanged as a fallback.

| File | Material | Plate selection | KAMP purge | Status |
|---|---|---|---|---|
| `creality-start-material-only.gcode` | Yes | No; loads `default` | No | PASS — Creality Print 7.1.1 |
| `creality-start-material-surface-profiles.gcode` | Yes | Yes | No | PASS — Creality Print 7.1.1 |
| `creality-start-material-kamp.gcode` | Yes | No; loads `default` | Yes | PASS — Creality Print 7.1.1 |
| `creality-start-material-surface-profiles-kamp.gcode` | Yes | Yes | Yes | PASS — Creality Print 7.1.1 |
| `orca-start-material-only.gcode` | Yes | No | No | Orca 2.4.2 standard workflow tested |
| `orca-start-material-kamp.gcode` | Yes | No | Yes | KAMP and enabled stock fallback tested |
| `orca-start-material-surface-profiles.gcode` | Yes | Yes | No | Exported plate names verified; full matrix pending |
| `orca-start-material-surface-profiles-kamp.gcode` | Yes | Yes | Yes | `high_temp` workflow tested; full matrix pending |
| `orca-machine-start.gcode` | Yes | Explicit `default` | Yes | Legacy filename; prefer the variants above |

The plate-selection variants pass `SURFACE=` to either the Cartographer plate
workflow or the optional stock-PR-Touch plate-aware mesh feature. On a
Cartographer setup it selects matching scan and touch models. On a stock-probe
setup it becomes part of the saved mesh profile name. The material-only and
KAMP-only variants intentionally omit `SURFACE=`; Cartographer then loads its
`default` models, while the stock-probe path retains its original
temperature-only mesh name. All eight variants pass `MATERIAL=` so
`START_PRINT` can apply the matching offset from `_START_PRINT_VARS`.

The four Creality Print variants were validated on printer firmware `1.1.5.5`.
See the repository [validation report](../../../../VALIDATION.md).

## Use

1. For either KAMP variant in Creality Print 7.x, enable **Exclude objects**
   under Process settings -> Others. **Label objects** alone is insufficient.
   In OrcaSlicer, enable **Label objects** or **Use exclude_object**.
2. Open the printer profile's **Machine start G-code** setting.
3. Replace the complete block with the desired template.
4. Save the profile and slice a test object.
5. Confirm the generated `START_PRINT` line contains the expected
   `MATERIAL=` value.
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
