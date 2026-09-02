# Axis Twist Compensation

Compensates for Z-height drift across the X axis. It can improve first layers,
but it may also hide a mechanical bed or gantry problem. Check the printer
mechanically before enabling this optional feature.

## Calibration

The installer performs a firmware restart and waits for K2 motor initialization.
When it completes successfully, run:

```gcode
G28
Z_TILT_ADJUST
AXIS_TWIST_COMPENSATION_CALIBRATE AUTO=TRUE SAMPLE_COUNT=10
SAVE_CONFIG
```
