# Screws Tilt Adjust

Adds K2 Plus and K2 Pro support for Klipper's `SCREWS_TILT_CALCULATE` command. The command
probes above each bed screw and reports how far and in which direction to turn
each adjustment knob.

The installer selects the screw positions for the detected model. The Plus
runs `Z_TILT_ADJUST` before probing. On the single-Z Pro, clear the finished
part from the plate before running `SCREWS_TILT_CALCULATE`. The command homes
all axes if any axis has lost its home, then probes the four screws.

The bundled screw coordinates describe physical locations on the bed. At run
time, the command reads the active probe's X/Y offsets and converts each point
to a safe toolhead target. Stock zero-offset probing keeps the original
positions, while Cartographer mounts shift automatically in the correct
direction. If an exact screw location is outside the area reachable by both
the toolhead and sensor, the command uses the closest point inside a 0.5 mm
boundary margin and reports that substitution before moving.

After a successful probing pass finishes and the probe session closes, the
command lowers the bed by up to 200 mm by default to provide room to remove the build
plate and reach the adjustment screws. The final position is automatically
limited to 0.5 mm below the configured Z maximum.

With the macro bundle installed, open **Bed Assist → STC Bed Drop** in Fluidd.
Save applies the distance to the next screw check and stores it in
`custom/overrides.cfg`. The editor uses the printer's configured Z maximum
minus 0.5 mm. Each move also accounts for the bed position after probing.
For example, a 100 mm setting appears as:

```ini
[screws_tilt_adjust]
bed_drop_distance: 100
```

This is additional travel from the position after probing, not an absolute Z
target. Use `0` to disable the final drop. Negative and non-finite values are
rejected. Larger distances remain capped at Z maximum minus 0.5 mm. The setting
does not change screw-to-screw travel speed or the final drop speed.

Install this module update through the installer updater so its protected
Klippy code reload runs. Manual file edits require a protected
configuration restart (`FIRMWARE_RESTART`).

Repeat the command and adjustments until the reported values are close to
zero. See Klipper's
[bed-screw adjustment guide](https://www.klipper3d.org/Manual_Level.html#adjusting-bed-leveling-screws-using-the-bed-probe)
for the procedure.

The installer adds a Klippy Python module and configuration, then performs the
protected Klippy host reload, firmware-reset recovery, and K2 motor
initialization wait before returning.
