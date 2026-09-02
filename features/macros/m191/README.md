# M191 Chamber Temperature Macro

Adds `M191 S<temperature>` to set and wait for the K2 Plus chamber
temperature.

For targets above 35 C, the macro can temporarily use the heated bed and
circulation fan to assist the chamber heater. Bed assistance is skipped when
the chamber is already at the requested temperature. After the chamber reaches
its target, the original bed target and circulation-fan power are restored.

The chamber exhaust target is set 2 C above the chamber-heater target so normal
sensor variation and control hysteresis do not make the heater and exhaust fan
fight each other. `M191 S0` turns off the heaters and fan.

This macro is called by the project's `START_PRINT` workflow when a chamber
temperature is supplied by the slicer.
