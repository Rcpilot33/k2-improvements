# Cartographer Fluidd Macros

Adds predefined `CARTO_*` buttons to Fluidd for Cartographer calibration,
model loading, homing, and diagnostics.

These macros are installed together with the
[surface-selection wrapper](../surface-selection-wrapper/README.md) by the
**Cartographer plate workflow** entry in Extras.

## Included plate profiles

The supplied buttons use three fixed model names:

- `default`
- `pei`
- `coolplate`

For each name, Fluidd receives buttons to calibrate the scan model, calibrate
the touch model, and load both saved models. Utility buttons provide touch
homing, model listing, and probe information.

The buttons call the Cartographer plugin commands directly, including
`CARTOGRAPHER_SCAN_CALIBRATE`, `CARTOGRAPHER_TOUCH_CALIBRATE`, and the scan and
touch model loaders.

## Custom plates

For another plate name, copy and rename the matching calibration and load
macros. Keep local changes in `custom/overrides.cfg` or another custom include
so repository updates do not overwrite them.

## Activation

The macros appear after Klipper reloads the configuration. Power-cycle the K2
Plus before the next `G28`.

## Credit

The predefined plate macros and their menu integration are adapted from
[erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24).
