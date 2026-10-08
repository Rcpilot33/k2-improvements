# Axis Twist Compensation

Compensates for Z-height drift across the X or Y axis. It can improve first layers,
but it may also hide a mechanical bed or gantry problem. Check the printer
mechanically before enabling this optional feature.

Calibration coordinates describe physical bed locations. Before moving, the
feature reads the active probe's effective X/Y offsets and the toolhead's
actual axis limits, then reduces the requested area when necessary. A stock
probe with zero offsets keeps the configured area. Front- or rear-mounted
Cartographer probes, including custom offsets, automatically shift the safe
calibration boundary in the corresponding direction.

On the stock-probe path, Creality's `prtouch_v3` normally reserves the
`axis_twist_compensation` object name for its internal probe correction shim.
The installer renames that alias to `k2_prtouch_axis_twist_status` so the full
Axis Twist module can load while leaving PR Touch itself active. Axis Twist
forwards the native object's complete live status under the original name.
This preserves Creality's `on_turb` fan-check suppression during intentional
fan shutdowns for homing and probing, along with `g28_nacc` and other fields.
Existing installs with the old registration-removal patch are upgraded in place.
The original `prtouch_v3.py` is retained beside
the installed file with a `.k2-axis-twist.bak` suffix.

The installed legacy probe bridge also exposes Klipper's current probe-parameter
accessor so Axis Twist can read the stock probe's lift speed and sampling
settings during Klippy startup.

## Calibration

The installer replaces loaded Klippy Python modules, then performs the
protected Klippy host reload, firmware-reset recovery, and K2 motor
initialization wait. When it completes successfully, run:

```gcode
G28
Z_TILT_ADJUST
AXIS_TWIST_COMPENSATION_CALIBRATE AUTO=TRUE SAMPLE_COUNT=10
SAVE_CONFIG
```

`SAMPLE_COUNT` applies to each axis in AUTO mode, so `SAMPLE_COUNT=10`
collects a 10 by 10 grid of 100 measurements. The console reports the active
probe offsets and calculated safe bed area before motion begins. Review that
line and the resulting correction arrays before running `SAVE_CONFIG`.
