# SAVE_CONFIG firmware restart protection

The K2 Plus can retain an unsafe motor-controller state after Klipper's normal
host-only restart. The first subsequent `G28` may then move in the wrong
direction. This has been reproduced with both the stock PR Touch and
Cartographer installation paths.

This shared core feature preserves Klipper's normal `SAVE_CONFIG` file update
and stock in-process restart. Immediately before that restart, it schedules a
detached worker which observes the old Klipper session disappear, waits for the
new session and `motor_control.motor_ready`, and then requests exactly one
`FIRMWARE_RESTART`. The worker again verifies both Klipper and motor-controller
readiness before reporting success. A runtime `SAVE_CONFIG` never restarts the
Linux Klippy service.

The stock-probe and Cartographer installers both install this feature. Its
initial installation replaces Klippy's `configfile.py`, so the installer uses
the same protected Klippy-code reload sequence. Runtime restart diagnostics
are written to `/tmp/k2-save-config-restart.log`, with the final state in
`/tmp/k2-save-config-restart.status`. If a protected restart fails, fully
power-cycle before homing.
