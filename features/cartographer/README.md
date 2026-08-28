# Cartographer

Cartographer replaces the K2 Plus stock contact probe with a fast scanning
probe. It supports dense, adaptive bed meshes without the long probing time of
a large stock-probe mesh.

## Benefits

- Faster bed scanning
- Denser mesh data
- Adaptive meshing around the current print
- Automatic inclusion of a detected Creality Print prime tower in the
  adaptive mesh
- Separate scan and touch models for supported plate workflows

## Important differences

The K2 Plus uses a userspace USB bridge for Cartographer communication. The
installation therefore includes the probe plugin, bridge service, Klipper
configuration, and K2-specific macros.

Installing Cartographer replaces the active stock `prtouch_v3` configuration.

The installer also adds a printer-side prime-tower scanner. Creality Print
does not label its prime tower as an exclude object, so its actual
`;TYPE:Prime tower` extrusion paths are read from the selected G-code file.
When normal object polygons are available, the detected tower footprint is
included automatically in the Cartographer adaptive mesh. Rotated, resized,
and normally layered towers use their real sliced motion rather than slicer
metadata. Prints without a tower retain the existing behavior.

Creality Print's **Prime tower -> No sparse layers (beta)** option is not
supported on the K2 Plus. A delayed tower can command the bed back to
first-layer height after the model is already tall, creating a collision risk.
If an actual prime-tower toolpath and that setting are both present, adaptive
mesh preflight rejects the file and directs the user to disable the option and
reslice. The managed `START_PRINT` macro performs the same check before any
printer preparation moves. A profile that retains the setting does not block
a file with no prime tower.

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
installation. The installer performs a firmware restart and waits for K2 motor
initialization before returning.

The Cartographer installation also supplies Creality's inter-print
`SAFE_MOVE_Z` compatibility command. It restricts the closed print service to
its observed Z=20 endpoint, performs the move only while the printer is idle,
and reports completion through `virtual_sdcard.run_dis` as the stock PR Touch
extension does. Cartographer does not provide the stock nozzle-pressure
collision sensing during this move.

On a direct Cartographer install or a conversion from the stock-probe setup,
the installer resets the PLA, PETG, ABS, ASA, DEFAULT, and PROBE offsets in
`custom/overrides.cfg` to zero. Those values are probe-dependent and must be
retuned for Cartographer. Other overrides are preserved. Rerunning the
installer when Cartographer is already configured preserves the existing
Cartographer offsets.

## Hardware

- [Cartographer V4 AIO Standard](https://cartographer3d.com/products/cartographer-v4-aio-standard), or
  Cartographer V3 USB hardware
- Two M2.6x20 mm screws
- Two M3x5x4 heat-set inserts for the printed mount
- A compatible K2 Plus Cartographer mount

## Install and calibrate

Use **Install or change setup -> Install Cartographer setup** from the menu.
After installation:

1. Select the mount and offset profile that matches the installed hardware.
2. Confirm the installer restart completed successfully; otherwise power-cycle
   before homing.
3. Follow the [Cartographer setup guide](./SETUP.md).
4. Flash probe firmware only if needed; firmware flashing is a separate menu
   action.

For automatic per-surface model selection, install the **Cartographer plate
workflow** from Extras and follow its
[selector/action guide](../../installer/extras/cartographer-macros/README.md).
