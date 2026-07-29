# Validation Status

## Firmware validation summary

The current menu/bootstrap redesign completed full install-and-print validation
on all three supported Creality firmware versions.

**Overall status: PASS**

### Installation paths

| Path | `1.1.3.13` | `1.1.5.2` | `1.1.5.5` |
|---|:---:|:---:|:---:|
| No-Cartographer / stock PR Touch | PASS | PASS | PASS |
| Add Cartographer over an existing no-Cartographer installation | PASS | PASS | PASS |
| Straight Cartographer installation | PASS | PASS | PASS |

Each firmware cycle included real prints rather than installation-only checks.
The completed tests covered stock and Cartographer startup, bed tilt and
meshing, Cartographer Touch homing, material-offset changes, KAMP and standard
purge profiles, plate selection, and switching between PLA and PETG.

Firmware `1.1.5.5` received the broadest optional-feature cycle. Firmware
`1.1.3.13` and `1.1.5.2` then repeated all three installation paths and the
core print workflows with the current code.

### Core print workflows

| Workflow | `1.1.3.13` | `1.1.5.2` | `1.1.5.5` |
|---|:---:|:---:|:---:|
| No-Carto temperature-specific mesh and print | PASS | PASS | PASS |
| Cartographer mesh, Touch home, and print | PASS | PASS | PASS |
| Material offsets and PLA/PETG switching | PASS | PASS | PASS |
| KAMP selectable independently by slicer profile | PASS | PASS | PASS |
| Cartographer plate selection and default fallback | PASS | PASS | PASS |

For the no-Cartographer path, a saved `default` mesh must match the active
`[bed_mesh] probe_count` before the first print. In particular, saved `5,5` and
`19,19` default meshes are not interchangeable.

### Features, extras, and detectors (`1.1.5.5` exhaustive cycle)

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

### Creality Print templates (`1.1.5.5` exhaustive cycle)

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

### Touch calibration and final print Z

`CARTOGRAPHER_TOUCH_CALIBRATE` selects and verifies the Touch detection
threshold and records the model speed. Its saved `z_offset` is only the
starting point for printing. Tune the actual first layer with live Z during a
print, then save that result to establish the final print Z for that model.

### Scope note: first-corner retraction

The first-corner behavior encountered during testing was traced to slicer
retraction/restart tuning and purge-to-slicer handoff, not to an installation,
probe, or K2 Improvements defect. The KAMP handoff correction is documented in
the [KAMP guide](./installer/extras/kamp-adaptive-purge/README.md).
