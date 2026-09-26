# Cartographer Fluidd Macros

Adds compact `A**_CARTO_*` buttons to Fluidd for Cartographer profile
selection, calibration, model loading, homing, and diagnostics.

The core Cartographer installer seeds Fluidd's UI metadata for all 17 buttons.
They appear in the **Cartographer Calibration** category with short aliases
while their real `A**_CARTO_*` names remain unchanged and retain their sorting
order. The default selector and shared calibration, loading, homing, and
diagnostic actions are visible immediately. The ten named plate selectors
remain hidden until the optional **Cartographer plate workflow** is enabled.
Plate selectors are green (`#1AED07`), the two calibration actions are orange
(`#FF9800`), and the remaining actions are blue (`#2196F3`). These colors
are installer-managed to keep the palette consistent. Original stock CP aliases migrate to slicer-qualified names. Other non-empty
aliases and valid category assignments are treated as user customizations and
preserved. Refresh Fluidd after installation to load a newly seeded layout.

All macros are installed with Cartographer. The **Cartographer plate workflow**
entry in Extras offers **Creality Print**, **OrcaSlicer**, or **Both**, reveals
only the chosen slicer's selectors, and installs the
[surface-selection wrapper](../surface-selection-wrapper/README.md).

## Slicer choice and Orca mapping

The selection is saved in `custom/plate-workflow-slicers.json` and reused by
updates and post-restart verification. Existing installations without a saved
choice retain CP selectors. Reopen the same Extras entry to change the choice.

Default comes first, then four CP selectors, then these six Orca selectors,
then the existing shared actions. Numeric sub-prefixes preserve existing
`A21`/`A22`/`A23` command names. Aliases show the plate name with
`(Creality Print)` or `(Orca)`; intentionally customized aliases are preserved.

| Orca display name | Exported `curr_bed_type` | Model / `SURFACE` | Numbered prefix |
|---|---|---|---|
| Smooth Cool Plate | Cool Plate | `orca_cool_plate` | `A16_CARTO_SELECT_ORCA_01` |
| Engineering Plate | Engineering Plate | `orca_engineering` | `A16_CARTO_SELECT_ORCA_02` |
| Smooth High Temp Plate | High Temp Plate | `high_temp` | `A16_CARTO_SELECT_ORCA_03` |
| Textured PEI Plate | Textured PEI Plate | `textured_pei` | `A16_CARTO_SELECT_ORCA_04` |
| Textured Cool Plate | Textured Cool Plate | `orca_textured_cool` | `A16_CARTO_SELECT_ORCA_05` |
| Cool Plate (SuperTack) | Supertack Plate | `orca_supertack` | `A16_CARTO_SELECT_ORCA_06` |

`high_temp` and `textured_pei` reuse existing CP models for the **same physical
plate**. Different physical plates needing different calibration require
separate custom models. Installation never renames or deletes saved models or
offsets. Calibrate and save Scan and Touch models for each new surface before
printing. Orca's unknown-plate fallback is `default`; it must match the fitted
plate.

All six internal names were captured from Orca 2.4.2 exports. The `high_temp`
print path passed printer testing; the expanded UI and other physical plate
calibrations still need printer validation. Automated tests check metadata,
persistence, and model-name contracts.

## Included plate profiles

The model names mirror the four bed types shown by Creality Print 7.1:

| Creality Print bed type | Cartographer model | Select button |
|---|---|---|
| Default / fallback | `default` | `A11` |
| Textured PEI Plate | `textured_pei` | `A12` |
| Epoxy Resin Plate | `epoxy` | `A13` |
| Smooth PEI / High Temp Plate | `high_temp` | `A14` |
| Customized Plate | `custom` | `A15` |

`default` is always visible as the manual fallback profile. The wrapper uses it
when `START_PRINT` is called without a `SURFACE` value; Creality Print's
explicit unknown-plate branch instead uses `textured_pei`.

Calibration always has two explicit steps. First click exactly one matching
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

The seeded aliases and colors, in macro-name order, are shown below. The ten
named plate aliases are hidden until the optional plate workflow is enabled.

```text
DEFAULT                 green
Textured PEI (Creality Print)          green
Epoxy Resin (Creality Print)           green
High Temp (Creality Print)             green
Customized (Creality Print)            green
Smooth Cool Plate (Orca)               green
Engineering Plate (Orca)               green
Smooth High Temp Plate (Orca)          green
Textured PEI Plate (Orca)               green
Textured Cool Plate (Orca)              green
Cool Plate (SuperTack) (Orca)           green
CARTO_SCAN_CALIBRATE    orange
CARTO_TOUCH_CALIBRATE   orange
CARTO_LOAD              blue
CARTO_TOUCH_HOME        blue
CARTO_LIST_MODELS       blue
CARTO_INFO              blue
```

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

The macros appear after Klipper reloads the configuration. When no print is
active, run `FIRMWARE_RESTART` and wait for the complete K2 startup sequence.
Power-cycle before the next `G28` only if that restart reports an error.

## Credit

The predefined plate macros and their menu integration are adapted from
[erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24).
