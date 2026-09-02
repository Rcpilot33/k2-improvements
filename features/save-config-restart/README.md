# SAVE_CONFIG firmware restart protection

The K2 Plus can retain an unsafe motor-controller state after Klipper's normal
host-only restart. The first subsequent `G28` may then move in the wrong
direction. This has been reproduced with both the stock PR Touch and
Cartographer installation paths.

This shared core feature preserves Klipper's normal `SAVE_CONFIG` file update
and changes its requested restart from a host-only restart to
`FIRMWARE_RESTART`, which also resets the printer MCU and motor controllers.

The stock-probe and Cartographer installers both install this feature. Its
initial installation replaces Klippy's `configfile.py`, so the installer uses
the protected Klippy-code reload sequence to start a fresh host process and
then reset the K2 MCUs. Once loaded, normal `SAVE_CONFIG` operations request
`FIRMWARE_RESTART`, wait for motor-controller startup, and verify that Klipper
remains ready. If a protected restart fails, fully power-cycle before homing.
