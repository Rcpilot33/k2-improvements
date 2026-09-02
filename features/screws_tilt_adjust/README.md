# Screws Tilt Adjust

Adds K2 Plus support for Klipper's `SCREWS_TILT_CALCULATE` command. The command
probes above each bed screw and reports how far and in which direction to turn
each adjustment knob.

Repeat the command and adjustments until the reported values are close to
zero. See Klipper's
[bed-screw adjustment guide](https://www.klipper3d.org/Manual_Level.html#adjusting-bed-leveling-screws-using-the-bed-probe)
for the procedure.

The installer adds a Klippy Python module and configuration, then performs the
protected Klippy host reload, firmware-reset recovery, and K2 motor
initialization wait before returning.
