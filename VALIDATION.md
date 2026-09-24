# Validation Status

## Cartographer plugin main rollout (September 2026)

The `main` installer now tracks the released Cartographer plugin `main` branch.
Its one-time update migration offers and completes the Cartographer action on an
existing install. The integration upgrade path passed on hardware; the promoted
`main` upgrade path remains the final test before tagging this release. This
rollout record is separate from the historical firmware matrix below. See
[the integration hardware record](DEPENDENCY_PRESERVATION.md#v3-hardware-validation-september-1920-2026)
for completed V3 checks and the remaining release gate. The overall historical
PASS below must not be read as blanket approval of every rollout path.

## Local automated tests

Run `python scripts/run_tests.py` from a development checkout. This discovers
Python unittest suites under bootstrap, features, installer, and scripts, using
an isolated process per test directory so duplicate module basenames and sibling
imports do not collide. It continues after failures and exits nonzero if any
directory fails. Tests requiring unavailable platform tools may report skips;
review those before claiming full coverage. Git and Bash are needed for installer
fixtures. Shell-only test scripts and printer hardware checks remain separate.
Root-level `pytest .` collection is not the supported runner.

## Firmware validation summary

The current menu/bootstrap redesign completed full install-and-print validation
on all three supported Creality firmware versions.

**Overall status: PASS**

In this report, `PASS` means the listed path or feature was installed on real
printer hardware, reached the expected ready state, and completed the
applicable calibration or print workflow. It does not mean that every hardware
revision, third-party mount, slicer version, filament, or optional combination
has been tested.

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
core print workflows with the current code. Firmware `1.1.5.2` also completed
the newer compatibility, offset-editor, Fluidd, and installer integration
checks listed below.

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

### Firmware `1.1.5.2` completion and added-workflow integration

| Test | Status |
|---|:---:|
| Complete Creality pre-file preparation retained with Cartographer and without PR Touch command errors | PASS |
| Creality touchscreen live Z-offset display and adjustment | PASS |
| Runtime-state pre-print case-fan override release | PASS |
| Bed tilt, Cartographer adaptive mesh, nozzle-clean handoff, Touch home, and print | PASS |
| Selected High Temperature plate Scan and Touch calibration, loading, and print path | PASS |
| Global Carto Touch Z Offset editor reads and rewrites saved Touch-model offsets | PASS |
| Material Z Offset editor reads and rewrites `overrides.cfg` values | PASS |
| Unknown `PLA-CF` uses the active `DEFAULT`, registers as `PLA_CF` at `0.050`, and remains restart-safe | PASS |
| Fluidd macro aliases, `Z Offsets` grouping, action colors, and phone layout | PASS |
| Combined Fluidd offset-dialog overlay retains the Creality camera service | PASS |
| Core macro repair followed by Cartographer plate-workflow repair and protected restart | PASS |
| Installer status detects Fluidd, Cartographer, macros, KAMP, and the plate workflow correctly | PASS |
| `G28` after the final installer and configuration restart sequences | PASS |

The first unknown-material print deliberately used the currently loaded
`DEFAULT` value of `0.060`, wrote `variable_offset_PLA_CF: 0.050` immediately
before `variable_offset_DEFAULT` in `overrides.cfg`, and did not interrupt the
print with an automatic restart. The saved material becomes active after a
Klippy restart, `FIRMWARE_RESTART`, or power cycle.

The `1.1.5.2` plate-calibration check used one selected plate to verify the
complete firmware-specific path. The five predefined selectors and their
shared Scan, Touch, and Load actions had already completed the exhaustive
plate-profile cycle on firmware `1.1.5.5`.

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
| Plate-aware saved meshes (stock PR Touch) | PASS |

### Restart and homing safety (`1.1.5.5`)

| Test | Status |
|---|:---:|
| Protected `SAVE_CONFIG` on stock PR Touch followed by `G28` (>10 consecutive cycles) | PASS |
| Protected `SAVE_CONFIG` on Cartographer followed by `G28` | PASS |
| Configuration-only installer `FIRMWARE_RESTART`, K2 initialization wait, and `G28` | PASS |
| Klippy-code installer host restart plus firmware-restart recovery | PASS |
| `screws_tilt_adjust` and `abort_homing` repair installs using the code-reload helper | PASS |

The repeated stock-probe test used a temporary `3,3` mesh to shorten each
cycle; the configured mesh was restored to `19,19` after testing. Moonraker can
report Klipper ready before the Creality motor-controller startup messages have
finished, so the shared helper waits an additional K2-specific stabilization
interval and verifies that Klipper is still ready before returning.

### Current Cartographer, KAMP, and chamber workflow (`1.1.5.5`)

| Test | Status |
|---|:---:|
| M191 bed assist only while below the requested chamber temperature | PASS |
| M191 restores the original slicer bed target after chamber heating | PASS |
| Chamber-fan target remains 2 C above the requested chamber target | PASS |
| Already-hot chamber skips bed assist without a macro parsing error | PASS |
| `CHAMBER_TEMP=0` print path | PASS |
| Prime tower included in Cartographer adaptive mesh at multiple locations | PASS |
| KAMP purge avoids the tower and selects front, left, or right safe corridors | PASS |
| No safe purge corridor warns and skips without leaving the usable area | PASS |
| Creality `No sparse layers (beta)` rejected only when an actual tower exists | PASS |
| Large 19.5 MB / 1,703-block tower file scan, adaptive mesh, and purge | PASS |
| Cancel, resend, fresh tower scan, mesh, and purge | PASS |
| Cartographer `SAFE_MOVE_Z` cancellation cleanup stays at or above Z=20 | PASS |

The large-file test completed its background prime-tower scan in about 107
seconds on the printer, then produced the expected adaptive mesh and KAMP
purge. The scanner uses a size-scaled timeout rather than a fixed small-file
limit. Its result is tied to the selected file identity; changing the selected
path, size, or modification time cancels stale work and starts another scan.

Creality Print's **Print Calibration** option was also reproduced separately.
It invoked a Creality-controlled 600-second bed-stabilization sequence at a
100 C bed target, set the chamber-fan target to 30 C, and sent the unsupported
`WAIT_BED_STABLE_END` command before this project's `START_PRINT`. This is an
incompatibility finding, not a supported workflow; the option must remain
disabled.

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

The names below are underlying macro names. With the Fluidd layout extra
installed, their display aliases include `DEFAULT`, `CARTO_SCAN_CALIBRATE`,
`CARTO_TOUCH_CALIBRATE`, and `CARTO_LOAD`, as shown in the installer checklist.

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

After calibration, run `SAVE_CONFIG` and wait for the protected firmware
restart to complete. Then select the intended profile again and use
`A23_CARTO_LOAD_SELECTED` when that saved model pair should become active. If
the restart reports an error, power-cycle before the next `G28`.

### Touch calibration and final print Z

`CARTOGRAPHER_TOUCH_CALIBRATE` selects and verifies the Touch detection
threshold and records the model speed. Its saved `z_offset` is only the
starting point for printing. Tune the actual first layer with live Z during a
print, then save that result to establish the final print Z for that model.

### Plate-aware saved mesh testing

The optional stock-PR-Touch plate-aware mesh feature completed hardware
validation on K2 Plus firmware `1.1.5.5` using the normal `19,19` probe count.

| Test | Status |
|---|:---:|
| Optional-extra installation and firmware restart | PASS |
| `SURFACE=<name>` creates/loads `<name>_<bed>c_<chamber>c` | PASS |
| Omitted `SURFACE` retains `<bed>c_<chamber>c` | PASS |
| Existing matching plate profile is reused | PASS |
| Different slicer plate selection uses a different profile | PASS |
| Plate-specific profile persists through protected `SAVE_CONFIG` | PASS |
| `variable_bed_mesh_soak: 0` skips the added missing-profile soak | PASS |
| Cartographer setup does not offer or install the extra | STATIC PASS |

Hardware tests covered omitted `SURFACE`, profile creation, protected
`SAVE_CONFIG`, restart persistence, and reuse without remeshing. Plate-aware
profiles were created for epoxy, high-temperature, and textured PEI plates.
Their saved matrices showed local differences up to `0.080 mm`, confirming
that the plate selector produced distinct and practically useful meshes. The
missing-profile soak was set to zero on an already heat-soaked printer and the
console reported `Soaking for 0.0 minutes` before beginning the mesh.

### Scope note: first-corner retraction

The first-corner behavior encountered during testing was traced to slicer
retraction/restart tuning and purge-to-slicer handoff, not to an installation,
probe, or K2 Improvements defect. The KAMP handoff correction is documented in
the [KAMP guide](./installer/extras/kamp-adaptive-purge/README.md).
