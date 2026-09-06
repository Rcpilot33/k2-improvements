# M191 Chamber Temperature Macro

Adds `M191 S<temperature>` to control the K2 Plus chamber temperature.
Targets from 1 through 35 C set the chamber heater and the cooling-fan target
to passive mode and return without waiting because Creality does not actively
heat the chamber in that range. Targets above 35 C enable the heater and wait
for the requested temperature.

For targets above 35 C, the macro can temporarily use the heated bed to assist
the chamber heater. During that active-heating path it homes when needed,
moves the bed down to Z=195 so it sits below the chamber heater, and runs the
model and side/auxiliary fans at 25% to circulate warm air. Bed assistance,
movement, and circulation are all skipped when the chamber is already at the
requested temperature.

After the chamber reaches its target, both circulation fans are turned off and
the original slicer-requested bed target is restored. Before returning to
`START_PRINT`, the macro waits until the measured bed temperature is within
5 C of that original nonzero target. A zero/off original bed target is restored
but does not cause an impossible wait for the bed to cool to 5 C.

The temperature-controlled **Chamber Fan** target is set 2 C above the exact
requested chamber-heater target so normal sensor variation and control
hysteresis do not make the heater and fan fight each other. The macro does not
silently raise or retain a higher chamber-heater target. `M191 S0` runs the
printer's heater-off and normal `M107` fan-off commands; that branch does not
issue a new temperature target to `chamber_fan`.

This macro is called by the project's `START_PRINT` workflow when a chamber
temperature is supplied by the slicer.
