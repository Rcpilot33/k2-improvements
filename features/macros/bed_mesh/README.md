# Bed Mesh Macros

The K2 Plus bed changes shape as it heats. A mesh created at room temperature
may not represent the bed at printing temperature.

These macros create temperature-specific mesh profiles after heating and
soaking the bed. On the stock probe path, an existing profile is reused when
available. Cartographer uses its adaptive mesh flow from `START_PRINT`.

Profiles are named from the requested bed and chamber temperatures, such as
`60c_0c`.
