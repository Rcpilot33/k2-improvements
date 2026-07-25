# KAMP Slicer Templates

These files replace the complete machine-start G-code block in a K2 Plus
slicer profile. Creality Print has three variants so users can enable either
feature independently or use both together. Keep Creality's stock profile as
the fourth, unchanged fallback profile.

| File | Plate selection | KAMP purge | Status |
|---|---|---|---|
| `creality-print-plate-selection-machine-start.gcode` | Yes | No | Creality Print 7.1.1 |
| `creality-print-kamp-machine-start.gcode` | No; loads `default` | Yes | Creality Print 7.1.1 |
| `creality-print-kamp-and-plate-selection-machine-start.gcode` | Yes | Yes | Creality Print 7.1.1 |
| `orca-machine-start.gcode` | Yes | Yes | Verify plate-name values against your profile |

The plate-selection variants pass `SURFACE=` to the printer's Cartographer
wrapper. The KAMP-only variant intentionally omits it, so the wrapper loads the
`default` scan and touch models on every print instead of retaining a model
from an earlier job.

## Use

1. For either KAMP variant, enable **Label objects** or
   **Use exclude_object** in the slicer.
2. Open the printer profile's **Machine start G-code** setting.
3. Replace the complete block with the desired template.
4. Save the profile and slice a test object.
5. For a KAMP variant, confirm the output contains `EXCLUDE_OBJECT_DEFINE`,
   `M109`, and `LINE_PURGE` before printing.
6. For a plate-selection variant, confirm the output contains the expected
   `SURFACE=` value before printing.

See the parent [KAMP guide](../README.md) for installation, verification,
tuning, and troubleshooting.
