# START_PRINT

Replaces the stock start macro with a temperature-aware workflow that:

- heats and optionally soaks the bed;
- waits for the requested chamber temperature;
- applies material-specific Z offsets;
- levels the gantry and prepares the correct bed mesh; and
- handles either Cartographer or the stock probe path.

## Slicer setup

Pass nozzle, bed, chamber, and material values from the slicer:

```gcode
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL={filament_type[initial_tool]}
```

Optional extensions such as KAMP or Cartographer plate selection may require
the complete machine-start templates supplied with those features. The four
validated Creality Print variants are documented in the
[slicer-template guide](../../../installer/extras/kamp-adaptive-purge/slicer-templates/README.md):

- material only;
- material + KAMP;
- material + surface profiles; and
- material + surface profiles + KAMP.

The material-only and KAMP-only templates intentionally omit `SURFACE=`, so
`START_PRINT` loads the `default` Cartographer models rather than retaining a
surface from an earlier print.
