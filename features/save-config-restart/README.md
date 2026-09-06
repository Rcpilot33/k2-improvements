# SAVE_CONFIG firmware restart protection

The K2 Plus can retain an unsafe motor-controller state after Klipper's normal
host-only restart. The first subsequent `G28` may then move in the wrong
direction. This has been reproduced with both the stock PR Touch and
Cartographer installation paths.

This shared core feature preserves Klipper's normal `SAVE_CONFIG` file update
and schedules the repository's protected restart worker after the file has
been replaced. The worker reloads Klippy, waits for the fresh host process to
settle, gives the K2 controllers a 25-second initialization interval before
`FIRMWARE_RESTART`, and then verifies that Klipper and the K2 motor controllers
remain ready.

The stock-probe and Cartographer installers both install this feature. Its
initial installation replaces Klippy's `configfile.py`, so the installer uses
the same protected Klippy-code reload sequence. Runtime restart diagnostics
are written to `/tmp/k2-save-config-restart.log`, with the final state in
`/tmp/k2-save-config-restart.status`. If a protected restart fails, fully
power-cycle before homing.
