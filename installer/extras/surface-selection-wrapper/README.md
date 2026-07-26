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

The Creality Print 7.1 workflow uses:

| Creality Print bed type | `SURFACE` and Cartographer model |
|---|---|
| Epoxy Resin Plate | `epoxy` |
| High Temp Plate | `high_temp` |
| Textured PEI Plate | `textured_pei` |
| Customized Plate | `custom` |

The selected `SURFACE` must have matching saved scan and touch models. The
wrapper falls back to `default` when `SURFACE` is omitted; the supplied
Creality Print template explicitly falls back to `textured_pei` for an
unrecognized bed type.

Creality Print users can copy one of these complete machine-start G-code
templates:

- [material pass only](../kamp-adaptive-purge/slicer-templates/creality-start-material-only.gcode), which loads `default`;
- [surface profiles](../kamp-adaptive-purge/slicer-templates/creality-start-material-surface-profiles.gcode);
- [KAMP only](../kamp-adaptive-purge/slicer-templates/creality-start-material-kamp.gcode), which omits `SURFACE` and loads `default`; or
- [surface profiles and KAMP](../kamp-adaptive-purge/slicer-templates/creality-start-material-surface-profiles-kamp.gcode).

Keep Creality's stock profile unchanged as a fallback. The KAMP templates
require the optional KAMP adaptive-purge feature; the plate-selection-only
template does not.

## Validation

On firmware `1.1.5.5`, the wrapper passed testing with all four Creality Print
templates. Explicit `SURFACE=` values loaded the matching model names, and
templates without `SURFACE=` loaded the `default` Scan and Touch models instead
of retaining the previous print's selection. See the repository
[validation report](../../../VALIDATION.md).

## Safety and updates

- The installer backs up `start_print.cfg` before modifying it.
- Re-running refreshes an older wrapper and is a no-op when it is current.
- If the expected insertion point is missing, installation stops without
  changing the file.
- A repository update may replace the patched upstream macro. If status shows
  this workflow as incomplete afterward, rerun it from Extras.

Power-cycle the printer before the next `G28` after the configuration reload.

## Credit

The automatic plate-selection workflow is adapted from
[erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24).
