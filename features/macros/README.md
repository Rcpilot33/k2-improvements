# K2 Plus Macro Bundle

Installs the four macro components used by both guided setup paths:

- [`START_PRINT`](./start_print/README.md)
- [`M191`](./m191/README.md)
- [temperature-aware bed mesh macros](./bed_mesh/README.md)
- `custom/overrides.cfg`

The overrides file is created only when missing. Re-running the installer
preserves existing mount selections and user changes.

Each macro is included from `custom/main.cfg`. The installers reload Klipper;
power-cycle the printer before the next `G28`.
