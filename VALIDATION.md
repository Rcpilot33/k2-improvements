# Validation Status

## Firmware 1.1.5.5

The current menu/bootstrap redesign and the workflows below completed a full
printer validation cycle on Creality firmware `1.1.5.5`.

**Overall status: PASS**

### Installation paths

| Path | Status |
|---|:---:|
| No-Cartographer / stock PR Touch | PASS |
| Add Cartographer over an existing no-Cartographer installation | PASS |
| Straight Cartographer installation | PASS |

### Features, extras, and detectors

| Feature or tool | Status |
|---|:---:|
| KAMP adaptive purge | PASS |
| R3MEN bed profile | PASS |
| Axis twist compensation | PASS |
| Secure Auth | PASS |
| Cartographer firmware flash tools | PASS |
| Factory reset and cleanup tools | PASS |
| Cartographer plate/surface wrapper | PASS |
| Cartographer Fluidd macro buttons | PASS |

### Creality Print templates

| Template | Status |
|---|:---:|
| `creality-start-material-only.gcode` | PASS |
| `creality-start-material-kamp.gcode` | PASS |
| `creality-start-material-surface-profiles.gcode` | PASS |
| `creality-start-material-surface-profiles-kamp.gcode` | PASS |

All four templates pass `MATERIAL=`. The two surface-profile variants pass the
selected `SURFACE=` value. The material-only and KAMP-only variants omit
`SURFACE=`, which intentionally makes `START_PRINT` load the `default`
Cartographer scan and touch models instead of retaining a model from an earlier
print.

### Cartographer surface/profile workflow

| Behavior | Status |
|---|:---:|
| `SURFACE` passes correctly from Creality Print | PASS |
| Missing `SURFACE` loads the `default` fallback | PASS |
| Surface/profile selector buttons | PASS |
| Selected Scan calibration | PASS |
| Selected Touch calibration | PASS |
| Selected Scan + Touch model loading | PASS |
| Model names match the selected profile | PASS |
| Fluidd macro sorting and readability | PASS |

The validated button sequence is:

1. Press exactly one selector:

   ```text
   A11_CARTO_SELECT_DEFAULT
   A12_CARTO_SELECT_TEXTURED_PEI
   A13_CARTO_SELECT_EPOXY
   A14_CARTO_SELECT_HIGH_TEMP
   A15_CARTO_SELECT_CUSTOM
   ```

2. Then press the required action:

   ```text
   A21_CARTO_SCAN_SELECTED
   A22_CARTO_TOUCH_SELECTED
   A23_CARTO_LOAD_SELECTED
   ```

A selector records the profile for the shared actions; it does not load a
model by itself. `A23_CARTO_LOAD_SELECTED` loads both the saved Scan and Touch
models. The selection resets to `default` after a Klipper restart.

After calibration, run `SAVE_CONFIG`, allow Klipper to restart, fully reboot or
power-cycle the printer before the next `G28`, select the intended profile
again, and use `A23_CARTO_LOAD_SELECTED` when that saved model pair should
become active.

## Other firmware

Firmware `1.1.3.13` and `1.1.5.2` passed the earlier installer and print
workflow. They still require a complete retest with the current menu/bootstrap
redesign before receiving the same current-validation status as `1.1.5.5`.
