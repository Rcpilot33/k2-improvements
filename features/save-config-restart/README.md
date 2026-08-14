# SAVE_CONFIG firmware restart protection

The K2 Plus can retain an unsafe motor-controller state after Klipper's normal
host-only restart. The first subsequent `G28` may then move in the wrong
direction. This has been reproduced with both the stock PR Touch and
Cartographer installation paths.

This shared core feature preserves Klipper's normal `SAVE_CONFIG` file update
and changes its requested restart from a host-only restart to
`FIRMWARE_RESTART`, which also resets the printer MCU and motor controllers.

The stock-probe and Cartographer installers both install this feature. After
installation or any restart-related recovery, fully power-cycle the printer
before the next homing test.
