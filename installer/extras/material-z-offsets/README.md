# Material Z Offsets

Optional Fluidd editor for the material offsets used by `START_PRINT`. It works
with either the stock probe or Cartographer.

The editor keeps material variables at the top of `_START_PRINT_VARS`, with
`DEFAULT` last. **Bed up / closer** makes a material offset more negative;
**Bed down / farther** makes it more positive. Save writes `overrides.cfg`
directly and updates the live `_START_PRINT_VARS` variables without restarting.
The next print uses the new values, and a restart reloads them from the file.
After saving changed material offsets, the editor discards staged Cartographer
Scan/Touch-model `z_offset` changes, restoring the autosave buffer to the values
already saved on disk. It does **not** run `SAVE_CONFIG` or `CXSAVE_CONFIG`.
Unrelated pending values (including changed calibration coefficients and meshes)
remain pending. New models without a saved offset are preserved. The pending-save
indicator clears only if nothing else is pending. Saved global offsets and live
Cartographer models/G-code offsets are not changed by this cleanup.
Cancel and Save with no material changes do not discard pending config.
If cleanup fails, material offsets remain saved/active and the error is reported.

When `START_PRINT` receives a new material name, the current print uses
`DEFAULT`. The helper saves the new material at `0.000` before `DEFAULT` so it
can be adjusted immediately. The current print still uses `DEFAULT`.

The installer also refreshes the managed `start_print.cfg` link so the apply
and automatic-registration handoff is active immediately after the installer's
protected restart. If the Cartographer plate workflow is already installed,
its surface-selection wrapper is reapplied after that refresh.
