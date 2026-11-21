# Validation Status

## K2 Pro bootstrap and diagnostics (November 20, 2026)

RC3, a stock-probe K2 Pro on firmware `1.1.8.3`, completed a fresh Entware
installation and cloned `k2-pro-support`. Accepting the bootstrap menu prompt
opened the read-only diagnostic, which identified model `F012` and board
`CR0CN200400C10` and returned to the SSH prompt.

After updating to `e5fc5fa`, RC3 opened the interactive K2 Pro Development
Installer. Selecting **1. Status and diagnostics** displayed the F012 report
and the component status list. Entware and better-root both showed as installed.

| Axis | Loaded stepper limits (mm) | Reported toolhead limits (mm) |
| --- | --- | --- |
| X | −13 to 302 | −9.3 to 302 |
| Y | −6.5 to 332 | −6.5 to 302 |
| Z | −10 to 303 | −10 to 303 |

The saved stepper limits matched the loaded settings. `PRINTER_PARAM` reported
a Y maximum of 302 mm. Moonraker reported `standby`, `motor_ready=true`, and
an empty `homed_axes` string. This run validates bootstrap and diagnostic
routing. Motion and recovery from a failed restart still need hardware tests.

### RC3 web interface and Moonraker baseline

On firmware `1.1.8.3`, nginx served Fluidd `v1.30.0` on port 4408.
Moonraker on port 7125 reported API `1.0.5`, Klippy ready, and no failed
components. Read-only requests returned heater temperatures, homing and print
state, file roots, database namespaces, and the webcam list.

The running service loaded `/usr/share/moonraker/moonraker.conf`.
Its Python components live directly under
`/usr/share/moonraker/components`. The Plus Fluidd installer expects
`printer_data/config/moonraker.conf` and the maintained Moonraker package
layout. The stock service lacks the `moonraker.common.RequestType` module
used by our bridge. The bridge status endpoint returned HTTP 404.

A read-only query to Creality's local WebSocket on port 9999 returned all
three fan percentages, printer and feed state, external-spool and four-slot
CFS data, humidity, and auto-refill status.

### Better Init hardware test

The Plus 1.1.8.0 firmware image and RC3’s stock
1.1.8.3 Klipper init script both register `/var/run/klippy.pid` and launch
Creality’s one-shot watcher, which sets Klippy’s `oom_score_adj` to `-500`.
Before Better Init was installed, `cat "/proc/$(cat /var/run/klippy.pid)/oom_score_adj"`
returned `-500` on RC3, confirming the adjustment on the running stock Klippy process.
On RC3 at commit `6fff16c`, the standalone Better Init installer restarted the
Klippy host, waited for motor readiness, and requested one `FIRMWARE_RESTART`
through stock Moonraker. Klippy and the motor controller both reported ready
afterward. The menu showed Better Init installed, and the same command returned
`-500` for the running Klippy process. The separate `save-config-restart`
component still awaited installation and testing.

On RC1, the K2 Plus, the same command returned `0` for its running Klippy process.

### RC3 maintained Moonraker hardware test

Option 5 completed on RC3. The running service used the dedicated
`moonraker-env` and loaded `/mnt/UDISK/printer_data/config/moonraker.conf`.
The checkout was `Rcpilot33/moonraker` branch `k2` at `ae1b034`, matching
the version reported by the running API. On port 7125, `/server/info` reported
API `1.5.0`, Klippy connected and ready, and empty lists for failed components,
warnings, and missing Klippy requirements. The printer reported `standby`
and `motor_ready=true`.

### RC3 Fluidd fan and CFS hardware test

Option 6 installed Fluidd `v1.37.5` on RC3. The operator confirmed that the
fan controls and both CFS actions, Feed and Retract, worked on the printer.
A read-only query to `/server/k2_device/status` reported a connected bridge
and matched the cards on port 4408. All three fans read 0%. Slot 1A showed
white Hyper-PLA at 20% remaining, the other slots and spool holder were empty,
CFS humidity was 28%, and auto-refill was on. Filament Deck was present on
this printer, so testing on a printer without it remains open.

### RC3 bed screw positions

With the stock probe, the operator jogged the nozzle to the four screw centers.
Fluidd showed front left (9, 59), front right (290, 59), rear right (290, 239),
and rear left (9, 239), in mm. RC3 exposes one Z stepper and has no
`Z_TILT_ADJUST` command. Option 7 installed successfully. RC3 offered the
one-time Screws Tilt Adjust update from `dfadef5`, and the operator applied it.
On November 21, the operator confirmed that running `SCREWS_TILT_CALCULATE`
from the Fluidd console with the axes unhomed homed the printer and probed all
four screws. Verification of knob turn direction and amount is still pending.

Fluidd showed a 0.0251 mm spread across the four screw positions on RC3.

| Screw | Probed Z (mm) | Difference from front left (mm) | Displayed adjustment |
| --- | ---: | ---: | --- |
| Front left | −0.1349 | 0.0000 | Base |
| Front right | −0.1290 | +0.0059 | 00:01 |
| Rear right | −0.1098 | +0.0251 | 00:02 |
| Rear left | −0.1320 | +0.0029 | 00:00 |

### RC3 Abort Homing

Option 9 applied the webhooks patch and completed the protected Klippy restart.
Afterward, Moonraker reported `webhooks.state=ready`,
`can_force_stop_homing=true`, and `print_stats.state=standby` with all axes
unhomed. Stopping an active homing move remains untested on RC3.

### RC3 SAVE_CONFIG restart protection

Option 10 completed the Klippy host reload and one protected firmware restart
on RC3. After installation, Moonraker reported Klipper ready, the printer in
standby, `motor_ready=true`, and `save_config_pending=false`. The config
directory contained five timestamped primary printer backups.

On November 21, the operator saved a 9×9 `default` bed mesh through Fluidd.
At 00:37:09 Klipper reported the config written and the protected restart
armed. It disconnected at 00:37:11, and Moonraker recorded one
`FIRMWARE_RESTART` at 00:37:43. Afterward, RC3 reported Klipper ready,
`motor_ready=true`, standby, and `save_config_pending=false`. The reloaded
config contained the saved mesh. Its first and last rows matched the Fluidd
save dialog. No mesh profile was active at the time of the read-only check.
The operator then ran `G28` and confirmed that RC3 homed correctly after
the protected restart.

### RC3 virtual SD-card upload guard

Option 11 installed both the trailing upload-boundary guard and the CFS
pause/refill file-position fix. The installed module's SHA-256 matched the
patch tested against RC3's original module. Both installer backups matched
the pre-install copy. After the protected restart, Moonraker reported Klipper
ready, `motor_ready=true`, standby, and an idle virtual SD reader. Handling a
trailing upload boundary and resuming after a CFS refill still need print tests
on RC3.

### RC3 core macro bundle review

Option 12 (memory diagnostics) is deferred. Before the F012 macro profile,
an offline render using the cube's `EXTRUDER_TEMP=220 BED_TEMP=50`
produced one `Z_TILT_ADJUST` with a matching temperature mesh and two when
the mesh had to be created. RC3 has one Z stepper and no Z tilt command.
Both paths emitted `G0 Y350` after the native chute command. RC3 reports
a normal Y maximum of 302 mm and a configured stepper maximum of 332 mm.

The F012 profile uses the factory chute command, single-Z preparation,
Z-driver mode, cleaning and fan handoff. The first trial build inherited
RC3's 9×9 mesh. The next stock-probe trial starts with an editable 19×19
grid in `custom/overrides.cfg`. Both M191 and the editor cap bed positions at the reported Z
maximum (303 mm on RC3). M191 follows the factory integer-temperature test
for active chamber heating. The stock-probe final home pairs
`NEXT_HOMEZ_NACCU` with `G28 Z` for both existing and newly generated meshes.
A prepared print with all axes homed and a saved matching mesh skips
the repeated home. Released axes force preparation again.

Offline tests cover those Pro paths. Across 384 comparisons, the Plus
rendered command lists matched the `integration-testing` reference for
START_PRINT, mesh lookup, mesh creation and M191, including Cartographer
Touch and Scan modes.

RC3 completed option 13 and the protected restart. A read-only Moonraker
check confirmed that the loaded `START_PRINT`, `_K2_PRO_FINAL_Z_HOME`,
`_CREATE_MESH` and `M191` macro bodies matched the tested files from
`e8c8f5f`. Klipper reported ready, the motor controller ready, the printer
in standby, all axes unhomed and no configuration warnings. The stock
PR Touch probe was configured with a 9×9 grid. Only the `default` mesh was
present and active. The mesh soak was five minutes. Fast Stop reported
both its command handler and stock mesh cancellation hook active.
The first physical print with this profile is pending.

The resume fan patch applied in memory to RC3's factory macro file, and the
installed Klippy command loop exposes the Fast Stop cancellation interface.
PR Touch cancellation and clearance behavior still need hardware validation.

### Fluidd follow-up

- [ ] Enable **Tool → Tools → SCREWS_TILT_CALCULATE** with unhomed axes when
  the K2 Pro auto-homing macro is installed. Fluidd `v1.37.5` disables the
  menu item before it can send the command. Keep the active manual-probe
  guard and the homing requirement for configurations that need it. Verify
  on RC3 that one selection homes and probes just as the console command does.

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

### Firmware `1.1.8.0` (November 18, 2026)

The maintainer confirmed that both no-Cartographer / stock PR Touch and
Cartographer setups have been run on firmware `1.1.8.0` with no issues. Both
setups are validated. The Cartographer installation route was not specified,
so a separate stock-to-Cartographer conversion result is not claimed.
This report does not extend every historical optional-feature test below to
`1.1.8.0`, or establish hardware validation of the new configurable bed drop.

### Historical full installation matrix

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

The names below are underlying macro names. The Cartographer installation
configures their persistent Fluidd display aliases, including `DEFAULT`,
`CARTO_SCAN_CALIBRATE`, `CARTO_TOUCH_CALIBRATE`, and `CARTO_LOAD`, as shown in
the installer checklist.

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
