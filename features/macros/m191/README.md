# M191 Chamber Temperature Macro

Adds `M191 S<temperature>` to set and wait for the K2 Plus chamber
temperature.

For targets above 35 C, the macro can use the heated bed and circulation fan
to assist the chamber heater. `M191 S0` turns off the heaters and fan.

This macro is called by the project's `START_PRINT` workflow when a chamber
temperature is supplied by the slicer.
