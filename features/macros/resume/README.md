# Resume fan restoration

The factory `RESUME_EXTERNAL` calculates fan restore values only for fans that
were on. It nevertheless uses both values afterward. For an off side fan this
produces `M106 P2 S F1` and interrupts the remaining macro commands.

This narrowly scoped patch initializes both restore values to zero before the
existing conditionals. Existing nonzero calculations, refill/loading, movement,
and tool mapping remain unchanged. It does not change PA or material identities.

Included in the Macros update. Requires confirmed idle state and a configuration
restart; no update is applied to an active print. The original macro file is
backed up as `gcode_macro.cfg.before-resume-fan-defaults`; unknown macro layouts
are refused instead of overwritten. Firmware replacement may require reapplying.
