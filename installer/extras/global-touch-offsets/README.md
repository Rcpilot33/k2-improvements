# Global Carto Z Offsets

This optional Cartographer feature adds a single `Global_Z_Offsets_Carto`
button in Fluidd's **Z Offsets** category. It reads
`variable_carto_final_z_mode` from `_START_PRINT_VARS` when opened and lists
the saved Cartographer Scan or Touch models for that mode. It does not assume
a fixed plate list, and a Scan-only setup does not need a Touch model.

The dialog keeps edits locally until **Save** is pressed. Select a
model, choose `0.005`, `0.010`, `0.025`, or `0.050` mm, then use the
physical-direction buttons:

- **Bed up / closer** makes the offset less negative.
- **Bed down / farther** makes the offset more negative.

Both model types are limited to `-5.000` through `0.000` mm. The dialog keeps
the mode it opened with, so changing the setting while the dialog is open
cannot redirect a save into the other model table.

**Cancel** discards all changes. **Save** writes only changed
`z_offset` values to their native `[cartographer scan_model ...]` or
`[cartographer touch_model ...]` sections,
runs Creality's non-restarting `CXSAVE_CONFIG`, and updates the live
Cartographer model table for the selected mode. The loaded model is refreshed
if it changed.
The values are available in the current session and reload from the saved
configuration after a restart. It never invokes `SAVE_CONFIG`.

The feature uses the settings dialogs included in the Rcpilot33 Fluidd release.
The installer checks that the installed build provides the required dialogs;
it does not replace Fluidd. Install the combined Fluidd release first.

Installation also performs the required Klippy code reload and protected
firmware restart automatically. Refresh Fluidd after installation so its
service worker loads the new dialog.

The shared capability check is under `installer/extras/fluidd-ui-overlay`.
