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

The workflow always has two explicit steps. First click exactly one matching
**Select** button:

```text
A11_CARTO_SELECT_DEFAULT
A12_CARTO_SELECT_TEXTURED_PEI
A13_CARTO_SELECT_EPOXY
A14_CARTO_SELECT_HIGH_TEMP
A15_CARTO_SELECT_CUSTOM
```

Then click the required shared action:

```text
A21_CARTO_SCAN_SELECTED
A22_CARTO_TOUCH_SELECTED
A23_CARTO_LOAD_SELECTED
```

The selector only records the profile for the shared actions; it does **not**
load a model. `A21` calibrates the selected Scan model, `A22` calibrates the
selected Touch model, and `A23` loads both existing models. Each action
explicitly uses the selected model instead of Fluidd's native calibration
buttons, which use the `default` model when called without a `MODEL=`
parameter.

To calibrate a plate, install that physical plate, select its profile, run
`A21_CARTO_SCAN_SELECTED`, and then separately run
`A22_CARTO_TOUCH_SELECTED`. Use `A23_CARTO_LOAD_SELECTED` when an existing pair
of saved models needs to be loaded. Run `SAVE_CONFIG` after calibration. After
the protected firmware restart completes, select the profile again before
loading it. Power-cycle before homing only if the restart reports an error.

Touch calibration finds and verifies the detection threshold and model speed;
it does not guarantee the final first-layer height. The Touch model's initial
`z_offset` must still be tuned during a real print. Use live Z to obtain the
correct first layer, then save that adjustment to establish the final print Z
for the selected model.

The numeric prefixes keep the selection and shared action buttons at the top
of Fluidd's alphabetical macro list. The selected profile resets to `default`
after a Klipper restart, so select a plate again before calibrating or loading.
Utility buttons provide touch homing, model listing, and probe information.

The buttons call the Cartographer plugin commands directly, including
`CARTOGRAPHER_SCAN_CALIBRATE`, `CARTOGRAPHER_TOUCH_CALIBRATE`, and the scan and
touch model loaders.

### Touch calibration starting threshold

`A22_CARTO_TOUCH_SELECTED` reads its default `START=` threshold from:

```ini
[gcode_macro _START_PRINT_VARS]
variable_carto_touch_calibrate_start: 500
```

The seeded value of `500` matches the Cartographer plugin default. Change the
value in `custom/overrides.cfg` to use a different minimum for every selected
Touch calibration. For example:

```ini
variable_carto_touch_calibrate_start: 2100
```

For a one-time test, the stored value can be overridden from the console:

```gcode
A22_CARTO_TOUCH_SELECTED START=2100
```

## Validation

The selector/action workflow passed printer testing on firmware `1.1.3.13`,
`1.1.5.2`, and `1.1.5.5`. The exhaustive `1.1.5.5` cycle included all five
selectors, selected Scan calibration, selected Touch calibration, combined
Scan + Touch loading, correct model names, and Fluidd sorting/readability. See
the repository [validation report](../../../VALIDATION.md).

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
