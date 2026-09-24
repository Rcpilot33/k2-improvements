# START_PRINT

Replaces the stock start macro with a temperature-aware workflow that:

- heats the bed and optionally soaks the complete machine after its requested
  bed and active chamber temperatures have been established;
- waits for chamber targets above Creality's 35 C active-heating threshold
  through `M191`, while lower nonzero targets are applied without blocking;
- restores the chamber cooling-fan target after Creality preparation: 35 C when
  no chamber temperature is requested, or the configured M191 margin above any
  nonzero requested chamber temperature;
- applies material-specific Z offsets;
- levels the gantry and prepares the correct bed mesh; and
- handles either Cartographer or the stock probe path.

On all firmware, the `BOX_NOZZLE_CLEAN` wrapper immediately releases any
nonzero direct case-fan request before entering Creality's native cleaning and
homing routine. It checks again afterward. `START_PRINT` also checks after
`BOX_START_PRINT`, then restores the requested temperature-based
chamber policy. The first nozzle-clean repeats the state-based release in case
Creality reasserted the direct request; an already-zero request remains a no-op.
This avoids depending on two Klipper objects that share the physical PA0 fan pin
to overwrite each other. The guard has been validated on firmware `1.1.3.13`,
`1.1.5.2`, and `1.1.5.5`.

Creality's heated-bed deformation calibration runs before the G-code file and
explicitly sends `M141 S30` followed by `M106 P1 S255`. The installed Klippy
command guard recognizes only that short idle pre-file sequence and suppresses
the direct case-fan request before it reaches the pin. Other `M106` commands,
including case-fan changes outside the two-second handoff, continue to use
Creality's original handler.

On the stock PR Touch path, the installer also guards the first `_HOME_Z` after
an artificial-coordinate `SAFE_MOVE_Z`. The guard recognizes that recovery
before motion from the Z=position_max relabel, its requested Z20 endpoint, and
the separately recorded physical Z; it does not depend on the photoelectric
home being positionally precise. If that preparation leaves the bed at a
logical position below Z=30, the bed first retreats to Z=30 at 6 mm/s and the
move is allowed to finish before the stock macro travels to the bed center.
That one-shot guard is consumed by the first `_HOME_Z`, so later Z-home passes
in the same print preparation do not repeat the retreat. Ordinary print-to-
print `SAFE_MOVE_Z` calls retain their stock Z20 behavior. This prevents an
early PR Touch contact from becoming a nozzle drag across the build plate. The
guard is inactive when `prtouch_v3` is not loaded.

When Cartographer or KAMP has installed the shared prime-tower scanner,
`START_PRINT` waits for that selected-file preflight before preparation moves.
Cartographer adaptive meshing includes a detected Creality Print prime tower
and expands the active mesh enough to contain the configured KAMP purge path.
The scan is bounded, cancelable, and rerun when a newly selected file identity
changes; a large G-code file can therefore add a visible preflight delay.

Leave Creality Print's **Print Calibration** option disabled. Its separate
Creality-controlled heat-soak and mesh sequence runs before `START_PRINT` and
is not compatible with this workflow.

`variable_heat_soak` is expressed in minutes. It runs after `M191` has reached
an active chamber target and restored any temporary bed-assist temperature, so
the delay stabilizes the machine at printing conditions rather than soaking the
bed before chamber heating. For passive chamber requests at or below 35 C, it
begins after the bed reaches its requested temperature. `SOAK_TIME=<minutes>`
on `START_PRINT` overrides the configured value for one print.

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
