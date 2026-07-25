# Cartographer Fluidd Macros

Adds predefined `CARTO_*` buttons to Fluidd for Cartographer calibration,
model loading, homing, and diagnostics.

These macros are installed together with the
[surface-selection wrapper](../surface-selection-wrapper/README.md) by the
**Cartographer plate workflow** entry in Extras.

## Included plate profiles

The model names mirror the four bed types shown by Creality Print 7.1:

| Creality Print bed type | Cartographer model | Fluidd macro suffix |
|---|---|---|
| Textured PEI Plate | `textured_pei` | `A21`–`A23` |
| Epoxy Resin Plate | `epoxy` | `A31`–`A33` |
| Smooth PEI / High Temp Plate | `high_temp` | `A41`–`A43` |
| Customized Plate | `custom` | `A51`–`A53` |

`default` remains available as a manual fallback profile. The wrapper uses it
when `START_PRINT` is called without a `SURFACE` value; Creality Print's
explicit unknown-plate branch instead uses `textured_pei`.

The numeric prefixes keep each plate's scan, touch, and load buttons together
at the top of Fluidd's alphabetical macro list. For every plate you use, run
its scan and touch calibration with the matching physical plate on the bed.
The matching load button manually loads both saved models.
Utility buttons provide touch homing, model listing, and probe information.

The buttons call the Cartographer plugin commands directly, including
`CARTOGRAPHER_SCAN_CALIBRATE`, `CARTOGRAPHER_TOUCH_CALIBRATE`, and the scan and
touch model loaders.

## Custom plates

The `custom` profile corresponds to Creality Print's **Customized Plate**
choice. For additional model names, copy and rename the matching calibration
and load macros. Keep local changes in `custom/overrides.cfg` or another custom
include so repository updates do not overwrite them.

## Activation

The macros appear after Klipper reloads the configuration. Power-cycle the K2
Plus before the next `G28`.

## Credit

The predefined plate macros and their menu integration are adapted from
[erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24).
