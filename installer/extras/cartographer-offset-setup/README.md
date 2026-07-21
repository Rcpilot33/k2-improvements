# cartographer-offset-setup

Switches between the Jamin/default and JimmyV Cartographer mounts by editing
only `custom/overrides.cfg`. It never modifies `custom/cartographer.cfg` or
`printer.cfg`.

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

### JimmyV back-mount

The installer writes the mount author's specified overrides:

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
- Reapplying the active profile is a no-op.
- Before a change, `overrides.cfg` is backed up beside the file with a
  `.before-cartographer-offset-<timestamp>` suffix.
- After a successful change, only the two newest backups created by this
  installer are retained; older matching backups are deleted.
- If either stock `[stepper_y]` value cannot be read from `printer.cfg`, the
  installer exits without changing anything.

## Activation

Run `FIRMWARE_RESTART` after switching. Follow the K2 Plus motor-state safety
procedure used by your firmware before the next home operation.
