# Material Z Offsets

Optional Fluidd editor for the material offsets used by `START_PRINT`. It works
with either the stock probe or Cartographer.

The editor keeps material variables at the top of `_START_PRINT_VARS`, with
`DEFAULT` last. **Bed up / closer** makes a material offset more negative;
**Bed down / farther** makes it more positive. Save & Restart writes
`overrides.cfg` directly and then runs `FIRMWARE_RESTART`.

When `START_PRINT` receives a new material name, the current print uses
`DEFAULT`. The helper saves the new material at `0.000` before `DEFAULT` so it
can be adjusted and activated by the next Save & Restart.

The installer also refreshes the managed `start_print.cfg` link so the apply
and automatic-registration handoff is active immediately after the installer's
protected restart. If the Cartographer plate workflow is already installed,
its surface-selection wrapper is reapplied after that refresh.
