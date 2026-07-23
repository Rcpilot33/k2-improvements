# KAMP Slicer Templates

These files replace the complete machine-start G-code block in the matching
K2 Plus slicer profile.

| File | Slicer | Status |
|---|---|---|
| `creality-print-machine-start.gcode` | Creality Print 7.x | Verified with 7.1.1 |
| `orca-machine-start.gcode` | Orca / OrcaSlicer | Verify plate-name values against your profile |

## Use

1. Enable **Label objects** or **Use exclude_object** in the slicer.
2. Open the printer profile's **Machine start G-code** setting.
3. Replace the complete block with the appropriate template.
4. Save the profile and slice a test object.
5. Confirm the output contains `EXCLUDE_OBJECT_DEFINE`, `M109`, and
   `LINE_PURGE` before printing.

See the parent [KAMP guide](../README.md) for installation, verification,
tuning, and troubleshooting.
