# START_PRINT

Replaces the stock start macro with a temperature-aware workflow that:

- heats and optionally soaks the bed;
- waits for the exact requested chamber temperature through `M191` without
  leaving the chamber heater at a hidden higher target;
- applies material-specific Z offsets;
- levels the gantry and prepares the correct bed mesh; and
- handles either Cartographer or the stock probe path.

On the stock-probe path, the installed macros also release Creality's one-time
100% case-fan command at the first nozzle-clean request. The fan is not
continuously managed afterward, so later manual changes still work. The
Cartographer path remains unchanged while its pre-print sequence is tested
separately.

When Cartographer or KAMP has installed the shared prime-tower scanner,
`START_PRINT` waits for that selected-file preflight before preparation moves.
Cartographer adaptive meshing includes a detected Creality Print prime tower
and expands the active mesh enough to contain the configured KAMP purge path.
The scan is bounded, cancelable, and rerun when a newly selected file identity
changes; a large G-code file can therefore add a visible preflight delay.

Leave Creality Print's **Print Calibration** option disabled. Its separate
Creality-controlled heat-soak and mesh sequence runs before `START_PRINT` and
is not compatible with this workflow.

## Slicer setup

Pass nozzle, bed, chamber, and material values from the slicer:

```gcode
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL={filament_type[initial_tool]}
```

Optional extensions such as KAMP, Cartographer plate selection, or stock-probe
plate-aware meshes may require the complete machine-start templates supplied
with those features. The four validated Creality Print variants are documented in the
[slicer-template guide](../../../installer/extras/kamp-adaptive-purge/slicer-templates/README.md):

- material only;
- material + KAMP;
- material + surface profiles; and
- material + surface profiles + KAMP.

The material-only and KAMP-only templates intentionally omit `SURFACE=`, so
`START_PRINT` loads the `default` Cartographer models rather than retaining a
surface from an earlier print. On the optional stock-probe plate-aware path,
omitting `SURFACE=` retains the existing temperature-only mesh name.
