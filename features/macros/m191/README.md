# M191 Chamber Temperature Macro

Adds `M191 S<temperature>` to set and wait for the K2 Plus chamber
temperature.

For targets above 35 C, the macro can temporarily use the heated bed and the
internal circulation fan (`fan2`) to assist the chamber heater. Bed assistance
is skipped when the chamber is already at the requested temperature. After the
chamber reaches its target, the original slicer-requested bed target and
circulation-fan power are restored.

The temperature-controlled **Chamber Fan** target is set 2 C above the exact
requested chamber-heater target so normal sensor variation and control
hysteresis do not make the heater and fan fight each other. The macro does not
silently raise or retain a higher chamber-heater target. `M191 S0` runs the
printer's heater-off and normal `M107` fan-off commands; that branch does not
issue a new temperature target to `chamber_fan`.

This macro is called by the project's `START_PRINT` workflow when a chamber
temperature is supplied by the slicer.
