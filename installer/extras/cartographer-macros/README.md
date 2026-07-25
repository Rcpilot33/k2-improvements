# Cartographer Fluidd Macros

Adds compact `A**_CARTO_*` buttons to Fluidd for Cartographer profile
selection, calibration, model loading, homing, and diagnostics.

These macros are installed together with the
[surface-selection wrapper](../surface-selection-wrapper/README.md) by the
**Cartographer plate workflow** entry in Extras.

## Included plate profiles

The model names mirror the four bed types shown by Creality Print 7.1:

| Creality Print bed type | Cartographer model | Select button |
|---|---|---|
| Default / fallback | `default` | `A11` |
| Textured PEI Plate | `textured_pei` | `A12` |
| Epoxy Resin Plate | `epoxy` | `A13` |
| Smooth PEI / High Temp Plate | `high_temp` | `A14` |
| Customized Plate | `custom` | `A15` |

`default` remains available as a manual fallback profile. The wrapper uses it
when `START_PRINT` is called without a `SURFACE` value; Creality Print's
explicit unknown-plate branch instead uses `textured_pei`.

First click the matching **Select** button. Then use the shared `A21` Scan,
`A22` Touch, or `A23` Load button. Each shared action explicitly uses the
selected model instead of Fluidd's native calibration buttons, which default to
the `default` model when called without a `MODEL=` parameter.

To calibrate a plate, install that physical plate, select its profile, run
`A21_CARTO_SCAN_SELECTED`, and then separately run
`A22_CARTO_TOUCH_SELECTED`. Use `A23_CARTO_LOAD_SELECTED` when an existing pair
of saved models only needs to be loaded.

The numeric prefixes keep the selection and shared action buttons at the top
of Fluidd's alphabetical macro list. The selected profile resets to `default`
after a Klipper restart, so select a plate again before calibrating or loading.
Utility buttons provide touch homing, model listing, and probe information.

The buttons call the Cartographer plugin commands directly, including
`CARTOGRAPHER_SCAN_CALIBRATE`, `CARTOGRAPHER_TOUCH_CALIBRATE`, and the scan and
touch model loaders.

## Custom plates

The `custom` profile corresponds to Creality Print's **Customized Plate**
choice. For additional model names, add another selection macro that updates
`_CARTO_PROFILE_STATE`; the shared Scan, Touch, and Load buttons need no
changes. Keep local additions in `custom/overrides.cfg` or another custom
include so repository updates do not overwrite them.

## Activation

The macros appear after Klipper reloads the configuration. Power-cycle the K2
Plus before the next `G28`.

## Credit

The predefined plate macros and their menu integration are adapted from
[erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24).
