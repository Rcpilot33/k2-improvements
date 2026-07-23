# Cartographer Automatic Plate Selection

Adds slicer-driven Cartographer model selection to `START_PRINT`. It is
installed together with the predefined
[Cartographer Fluidd macros](../cartographer-macros/README.md) by the
**Cartographer plate workflow** entry in Extras.

## How it works

The slicer passes `SURFACE=<name>` to `START_PRINT`. The wrapper loads the scan
and touch models with that name:

```gcode
CARTOGRAPHER_SCAN_MODEL LOAD=<name>
CARTOGRAPHER_TOUCH_MODEL LOAD=<name>
```

The supplied workflow uses `default`, `pei`, and `coolplate`. If `SURFACE` is
omitted, it falls back to `default`.

Use the machine-start G-code templates supplied with the optional print
workflow features, or add a matching `SURFACE` value to your existing slicer
configuration.

## Safety and updates

- The installer backs up `start_print.cfg` before modifying it.
- Re-running is a no-op when the wrapper is already present.
- If the expected insertion point is missing, installation stops without
  changing the file.
- A repository update may replace the patched upstream macro. If status shows
  this workflow as incomplete afterward, rerun it from Extras.

Power-cycle the printer before the next `G28` after the configuration reload.

## Credit

The automatic plate-selection workflow is adapted from
[erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24).
