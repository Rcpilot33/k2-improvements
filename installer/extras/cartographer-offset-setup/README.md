# Cartographer Mount Offset Setup

After selecting a JimmyV mount, configure **Optional extras -> JimmyV AI /
nozzle USB power protection** to disable factory nozzle-camera AI. Explicitly
enable its USB-power mode only if Cartographer is wired to the switched
factory nozzle-camera USB connector. A mount selection alone does not imply
that wiring choice.

Switches among the Jamin/default, JimmyV legacy, and JimmyV final Cartographer
mounts by editing only `custom/overrides.cfg`. It never modifies
`custom/cartographer.cfg` or `printer.cfg`.

## Profiles

### Jamin/default

The installer removes only these mount-related keys from `overrides.cfg`:

- `[cartographer] x_offset` and `y_offset`
- `[bed_mesh] mesh_min` and `mesh_max`
- `[stepper_y] position_endstop` and `position_min`

With those overrides absent, the values in `cartographer.cfg` are effective:

| Setting | Value |
| --- | --- |
| `cartographer y_offset` | `-15` |
| `bed_mesh mesh_min` | `10, 5` |
| `bed_mesh mesh_max` | `340, 330` |
| `stepper_y position_endstop` | `-0.4` |
| `stepper_y position_min` | `-0.4` |

### JimmyV legacy back-mount

This profile has not been tested on printer hardware in this fork. The
installer retains the offsets from JimmyV's earlier mount documentation for
users who already have that mount:

| Setting | Value |
| --- | --- |
| `cartographer y_offset` | `36` |
| `bed_mesh mesh_min` | `5, 36` |
| `bed_mesh mesh_max` | `345, 340` |

JimmyV also says to comment out the `[stepper_y]` `-0.4` values in
`cartographer.cfg`. Because this repository keeps `cartographer.cfg` unchanged,
the installer reads the stock `position_endstop` and `position_min` from
`printer.cfg` and writes them to `[stepper_y]` in `overrides.cfg`. The later
override has the same effective result.

### JimmyV final back-mount without 3DO camera

This profile has not been tested on printer hardware in this fork. Its values
come from JimmyV's final published model page:

| Setting | Value |
| --- | --- |
| `cartographer y_offset` | `12` |
| `bed_mesh mesh_min` | `5, 12` |
| `bed_mesh mesh_max` | `345, 340` |

The installer restores the stock `printer.cfg` stepper-Y values through
`overrides.cfg`, as described for the legacy profile.

### JimmyV final back-mount with 3DO camera

This profile has not been tested on printer hardware in this fork. It is for
JimmyV's final mount with the 3DO v2 nozzle camera:

| Setting | Value |
| --- | --- |
| `cartographer y_offset` | `17` |
| `bed_mesh mesh_min` | `5, 17` |
| `bed_mesh mesh_max` | `345, 340` |

The installer restores the stock `printer.cfg` stepper-Y values through
`overrides.cfg`, as described for the legacy profile.

Source for both final profiles: [JimmyV's final Cartographer rear-mount model](https://www.crealitycloud.com/model-detail/cartographer-rear-mount-3do-nozzle-camera?profileId=6a7b9ef075286de2e713afa8).

### Custom mount

The custom picker accepts:

- `x_offset` and `y_offset` (validated from -100 through 100)
- `mesh_min` and `mesh_max` as `X, Y` coordinate pairs
- Cartographer baseline or stock `printer.cfg` values for `[stepper_y]`

Custom values are written to `overrides.cfg`; `cartographer.cfg` remains
unchanged. Choosing the Cartographer stepper baseline leaves the `[stepper_y]`
keys absent from the overrides so the `-0.4` baseline remains effective.

Before showing the profile menu, the installer displays the current
`cartographer.cfg` X/Y offsets, mesh limits, and stepper Y values. These provide
a reference for custom-mount setup and become the custom-entry defaults when
the same key is not already present in `overrides.cfg`.

## Preservation and safety

- Existing unrelated settings, including `[bed_mesh] probe_count`, are kept.
- The picker can be rerun at any time to switch profiles.
- Reapplying the active profile is a no-op unless a JimmyV profile still has
  the incompatible stock nozzle-camera extra installed.
- Every JimmyV profile locks out the stock nozzle-camera stream. Selecting
  one removes that managed extra, with recovery backups, without switching
  off the shared USB rail. The 3DO camera and enclosure camera are untouched.
- Before a change, `overrides.cfg` is backed up beside the file with a
  `.before-cartographer-offset-<timestamp>` suffix.
- After a successful change, only the two newest backups created by this
  installer are retained; older matching backups are deleted.
- If either stock `[stepper_y]` value cannot be read from `printer.cfg`, the
  installer exits without changing anything.

## Activation

After a standalone mount change, the picker automatically performs the protected
`FIRMWARE_RESTART` and waits for Klipper and K2 motor initialization before
returning. It refuses changes while printing or paused, or if Moonraker cannot
confirm an idle state. Cancel and no-change selections do not restart anything
unless incompatible stock-camera removal is needed.

During full Cartographer setup, activation is deferred to the workflow's one
final protected restart. If a restart fails, the saved settings remain on disk;
check Fluidd and power-cycle before homing. Reapplying those same saved settings
is a no-op, so use Maintenance's protected restart action to retry activation.
