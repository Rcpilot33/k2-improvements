# Global Carto Touch Z Offsets

This optional Cartographer feature adds a single `Global_Z_Offsets_Carto`
button in Fluidd's **Z Offsets** category. It discovers the saved
Cartographer Touch models instead of assuming a fixed plate list.

The dialog keeps edits locally until **Save** is pressed. Select a
Touch model, choose `0.005`, `0.010`, `0.025`, or `0.050` mm, then use the
physical-direction buttons:

- **Bed up / closer** makes the Touch offset less negative.
- **Bed down / farther** makes the Touch offset more negative.

**Cancel** discards all changes. **Save** writes only changed
`z_offset` values to their native `[cartographer touch_model ...]` sections,
runs Creality's non-restarting `CXSAVE_CONFIG`, and updates the live
Cartographer Touch-model table. The loaded model is refreshed if it changed.
The values are available in the current session and reload from the saved
configuration after a restart. It never invokes `SAVE_CONFIG`.

The feature uses the tested shared Z-offset overlay for Jacob Fluidd
`v1.37.4` carried inside this repository. The shared archive contains both
optional Z-offset dialogs so installing either editor cannot remove the other
one. It does not use or update another Fluidd repository. The installer
verifies the installed version, preserves the original pre-overlay web files,
swaps in the bundled build, and restarts nginx. Reinstalling the core Fluidd
component restores Jacob's unmodified build.

Installation also performs the required Klippy code reload and protected
firmware restart automatically. Refresh Fluidd after installation so its
service worker loads the new dialog.

The shared bundle and reproducible source patch are under
`installer/extras/fluidd-ui-overlay`.
