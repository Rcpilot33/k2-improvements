# Bed Mesh Macros

The K2 Plus bed changes shape as it heats. A mesh created at room temperature
may not represent the bed at printing temperature.

These macros create temperature-specific mesh profiles after heating and
soaking the bed. On the stock probe path, an existing profile is reused when
available. Cartographer uses its adaptive mesh flow from `START_PRINT`.

Profiles are named from the requested bed and chamber temperatures, such as
`60.0c_0.0c`. The optional
[plate-aware mesh feature](../../../installer/extras/plate-aware-mesh/README.md)
can prefix that name with the slicer's selected build plate on stock PR Touch
installations, while retaining the temperature-only format when no plate is
passed.

The missing-mesh heat soak defaults to five minutes and is configurable in
`custom/overrides.cfg`:

```ini
variable_bed_mesh_soak: 5
```

Set it to `0` when the printer is already heat soaked before a print is sent.
This skips only the additional delay before creating a missing saved mesh; all
requested temperature waits, tilt adjustment, homing, cleaning, and probing
still run.

## Stock PR Touch prerequisite

On a no-Cartographer / stock PR Touch installation, create and save a
`default` mesh before the first print. That mesh must be generated with the
same `[bed_mesh] probe_count` that is currently configured.

Recreate and save `default` whenever `probe_count` changes. Mesh dimensions are
not interchangeable: a saved `5,5` default mesh cannot be used with an active
`19,19` configuration, and a saved `19,19` mesh cannot be used with `5,5`.
Keeping the saved default mesh and active probe count matched avoids a
first-print stall or mesh-processing failure.
