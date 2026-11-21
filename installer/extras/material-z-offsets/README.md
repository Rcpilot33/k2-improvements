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

The core Macros install handles material registration on the K2 Plus and Pro.
When `START_PRINT` first receives `Hyper-PLA`, for example, it applies
`DEFAULT` to that print and writes `variable_offset_HYPER_PLA: 0.000` to
`custom/overrides.cfg`. The next print with that material uses its own entry.
Install the optional Fluidd editor to adjust those values live.

The installer also refreshes the managed `start_print.cfg` link so the apply
and automatic-registration handoff is active immediately after the installer's
protected restart. If the Cartographer plate workflow is already installed,
its surface-selection wrapper is reapplied after that refresh.
