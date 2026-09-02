# Prime-Tower Preflight Scanner

This internal Klippy extension detects the actual extrusion footprint of a
Creality Print prime tower before printer preparation begins. Creality Print
does not emit an `EXCLUDE_OBJECT_DEFINE` polygon for its tower, so Cartographer
adaptive meshing and KAMP cannot otherwise reserve that occupied area.

Users do not install this component directly. The Cartographer and KAMP
installers both install it and perform the required protected Klippy host
reload and firmware-reset recovery.

## Behavior

- The parser reads actual `;TYPE:Prime tower` extrusion motion rather than
  trusting tower metadata, so rotated and resized towers use their sliced
  footprint.
- The scan runs in a background worker. `PRIME_TOWER_WAIT` cooperatively waits
  for completion before `START_PRINT` moves the printer.
- Selecting a different file cancels obsolete work. The result is keyed to the
  selected path, size, and modification time.
- The default timeout is at least 120 seconds and scales to 10 seconds per MiB
  for larger files. A timeout or parse failure is fail-open: printing continues
  without tower geometry and reports the reason.
- A real tower combined with Creality Print's **No sparse layers (beta)** is
  fail-closed because that delayed-tower behavior can cause a collision. The
  print is rejected before preparation and the heaters are turned off.
- During a pending scan, `START_PRINT` holds the sliced bed/chamber targets and
  a 140 C nozzle preheat after Creality's virtual-SD preamble resets them.

Successful scans log the block count, footprint bounds, file size, and elapsed
time in `klippy.log`. The public workflows and slicer requirements are covered
in the [Cartographer guide](../cartographer/README.md) and
[KAMP guide](../../installer/extras/kamp-adaptive-purge/README.md).
