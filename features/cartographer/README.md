# Cartographer

Cartographer replaces the stock contact probe on the K2 Plus and K2 Pro with a fast scanning
probe. It supports dense, adaptive bed meshes without the long probing time of
a large stock-probe mesh.

## Benefits

- Faster bed scanning
- Denser mesh data
- Adaptive meshing around the current print
- Automatic inclusion of the complete sliced first layer in the adaptive mesh
- Separate scan and touch models for supported plate workflows

## Important differences

Both printers use a userspace USB bridge for Cartographer communication. The
installation therefore includes the probe plugin, bridge service, Klipper
configuration, and K2-specific macros.

Jacob10383 wrote `usb_bridge_new`, distributed here as a binary with no published source. SHA-256: `acab226e89a065f4255906196e52ea6f6f3fcb0d2bf2f3ef7a765a625fb707df`.

Installing Cartographer replaces the active stock `prtouch_v3` configuration.
Creality's master service uses that section name to select its complete
pre-file preparation path. The installer therefore reports an empty synthetic
`prtouch_v3` status object and empty config section during Klipper connection.
This preserves the stock preparation selection without loading the physical
PR-Touch driver, claiming probe pins, or replacing Cartographer.

The installed Cartographer configuration also supplies safe compatibility
no-ops for the stock macros' `PRES_CHECK`, `NOZZLE_CLEAR`, and
`NEXT_HOMEZ_NACCU` calls. Their original pressure-sensor behavior does not
apply to Cartographer; physical brush cleaning continues through
`BOX_NOZZLE_CLEAN`.

The installer also adds a printer-side first-layer scanner. It reads actual
positive-extrusion motion between the first two layer-change markers, so the
Cartographer adaptive mesh covers models, brims, skirts, supports, and a prime
tower even when those features are absent from exclude-object polygons.

The scan runs in a background worker, is cooperatively cancelable, and stops at
the second layer marker. `START_PRINT` waits for the result before preparation.
The console reports scan time, combined bounds, margin, and requested mesh;
`klippy.log` records move count, bounds, file size, and elapsed time.
Implementation details and timeout behavior are documented in the shared
[prime-tower scanner guide](../prime_tower/README.md).

Creality Print's **Prime tower -> No sparse layers (beta)** option is not
supported by the adaptive mesh workflow. A delayed tower can command the bed back to
first-layer height after the model is already tall, creating a collision risk.
If an enabled prime tower and that setting are both present, adaptive mesh
preflight rejects the file and directs the user to disable the option and
reslice. An explicitly disabled tower does not make a retained setting unsafe.

The installer also adds a status-only compatibility layer for the stock K2
touchscreen. Creality's live Z-offset page reads the nonstandard
`probe.z_offset` status field. Cartographer normally omits that field, which
leaves the value blank even though live adjustment works. The compatibility
layer publishes the inverse of Klipper's live `gcode_move.homing_origin.z`
adjustment through that field because Creality's screen negates the stock
probe value for display. Klipper's existing object subscription sends changes
to the screen. The layer does not poll Fluidd, issue G-code, or move an axis.

After installation, `K2_CARTOGRAPHER_TOUCHSCREEN_STATUS` reports both the live
`z_offset` shown by Fluidd and the inverse `probe_z_offset` published to the
touchscreen.

Choose the correct physical mount preset before the first homing move after
installation. The guided Cartographer path offers the mount-offset picker
before its final protected Klippy-code reload, firmware-reset recovery, and K2
motor-initialization wait.

The Cartographer installation also supplies Creality's inter-print
`SAFE_MOVE_Z` compatibility command. It permits only negative Z travel that
stops at or above the observed Z=20 clearance floor, performs the move only
while the printer is idle, and reports completion through
`virtual_sdcard.run_dis` as the stock PR Touch extension does. The endpoint may
remain above Z=20 when Creality's service calculated its relative travel before
cancellation cleanup finished. Cartographer's scan endstop guards the move. On
Creality's artificial-Z recovery path, the move stops at either a Cartographer
trigger or the guarded Z=30 clearance endpoint. K2-Improvements can use Z30
because it does not use the AI cameras that require Creality's Z20 inspection
height. If Cartographer triggers before that endpoint, the bed retreats 10 mm.
The artificial path acknowledges
Creality's original requested distance while logging the shorter physical
travel; this prevents the closed service from commanding the bed toward Z20.
An unexpected trigger during a normal between-print move stops that command
without reporting completion.

On a direct Cartographer install or a conversion from the stock-probe setup,
the installer resets the PLA, PETG, ABS, ASA, and DEFAULT offsets in
`custom/overrides.cfg` to zero. Those values are probe-dependent and must be
retuned for Cartographer. Other overrides are preserved. Rerunning the
installer when Cartographer is already configured preserves the existing
Cartographer offsets.

If a plugin refresh refuses to proceed, preserve the affected path before
retrying: move aside a non-Git plugin directory; commit or copy out tracked
changes; verify `origin` is either the supported upstream or Rcpilot33 fork;
and preserve divergent local commits on a separate branch. The installer
deliberately never deletes or resets those states automatically.

## Stationary Scan probe positioning

The K2 compatibility module `k2_cartographer_probe_wait` waits for queued
positioning moves to finish before calling Cartographer's stationary Scan
probe. This prevents its five-second usable-sample timeout from expiring while
the bed is still rising from a lowered position for `Z_TILT_ADJUST` or
`SCREWS_TILT_CALCULATE`. It also covers stationary `PROBE` and
`PROBE_ACCURACY` calls.

The original sample timeout and probe calculations remain in the plugin.
The module does not change movement speed, screw-access bed lowering,
continuous scan meshing, Touch probing, K2 endstop homing, calibration models,
temperature compensation, or saved offsets. It modifies only this printer's
Scan probe entry point, not the plugin checkout or shared sample collector.
Unsupported plugin interfaces stop configuration rather than silently omitting
the protection. Shutdown while waiting aborts before sampling resumes.

Existing Cartographer installs receive this through migration
`cartographer-stationary-probe-motion-wait-v1` and the protected Klippy restart.
`klippy.log` records `K2 Cartographer stationary Scan probe motion wait installed`,
and `k2_cartographer_probe_wait.installed` reports activation. No re-mesh or
offset adjustment is required solely for this timing fix. Hardware validation
should include screws tilt from a lowered bed, normal Z tilt, homing, Touch,
and a continuous scan mesh.

## Hardware

- [Cartographer V4 AIO Standard](https://cartographer3d.com/products/cartographer-v4-aio-standard), or
  Cartographer V3 USB hardware
- Two M2.6x20 mm screws
- Two M3x5x4 heat-set inserts for the printed mount
- A Cartographer mount compatible with your printer model

## Install and calibrate

Use **Install or change setup -> Install Cartographer setup** from the menu.
After installation:

1. Select the mount and offset profile that matches the installed hardware.
2. Confirm the protected Klippy-code reload and firmware-reset sequence
   completed successfully; otherwise power-cycle before homing.
3. Follow the [Cartographer setup guide](./SETUP.md).
4. Flash probe firmware only if needed; firmware flashing is a separate menu
   action.

The installed bed-mesh defaults are `probe_count: 50,50` and `speed: 150` in
`custom/overrides.cfg`. Speed `200` can be set for Full firmware after sample
coverage is verified. The shared no-Cartographer template remains `19,19`.

For automatic per-surface model selection, install the **Cartographer plate
workflow** from Extras and follow its
[selector/action guide](../../installer/extras/cartographer-macros/README.md).

## USB bridge binary

On systems that need the userspace USB bridge, the installer uses the ARM
binary introduced in Jacob10383's commit `68d6758`. Its SHA-256 is
`acab226e89a065f4255906196e52ea6f6f3fcb0d2bf2f3ef7a765a625fb707df`.
The upstream commit supplies the binary. Its build source and a separate
distribution license have not been verified.
[Upstream bridge commit](https://github.com/Jacob10383/k2-improvements/commit/68d6758a2242014db8624e872286c88814b24d2d)
