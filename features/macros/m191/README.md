# M191 Chamber Temperature Macro

Adds `M191 S<temperature>` to control the K2 Plus chamber temperature. Targets
from 1 through 35 C put the chamber heater in passive mode and return without
waiting because Creality does not actively heat the chamber in that range.
Targets above 35 C enable the heater and wait for the requested temperature.
While M191 is waiting, its once-per-second temperature report adds
`C:<actual> /<target>` using the same `temperature_sensor chamber_temp`
measurement that controls the wait. The bed and tool values remain in the
standard Klipper report.

## Configuration

The installer keeps these settings in `[gcode_macro _M191_VARS]` within
`custom/overrides.cfg`. Reinstalling or updating the macros adds settings that
are missing but does not overwrite existing values.

| Variable | Default | Valid range | Purpose |
| --- | ---: | ---: | --- |
| `bed_assist_enabled` | `1` | `0` or `1` | Enables or disables the complete bed-move and circulation assist sequence. |
| `bed_assist_trigger_delta` | `3.0` | `0` to `20` C | Starts assistance only when the chamber is more than this far below its requested temperature. |
| `bed_assist_bed_target` | `105.0` | above `0` to `120` C | Fixed temporary bed target used when the degrees-above setting is zero. |
| `bed_assist_degrees_above_commanded` | `0.0` | `0` to `120` C | When above zero, calculates the assist target by adding this value to the slicer's commanded bed temperature. |
| `bed_assist_z_height` | `195.0` | `30` to `330` mm | Bed position used to circulate warm air below the chamber heater. |
| `circulation_fan_speed` | `15.0` | `0` to `100` percent | Low model and side/auxiliary fan speed during assistance. The existing key is retained for upgrade compatibility. |
| `circulation_fan_high_speed` | `100.0` | low speed to `100` percent | High model and side/auxiliary fan speed during assistance. |
| `circulation_fan_low_seconds` | `45.0` | above `0` to `600` seconds | Time spent at the low circulation speed before changing to high. |
| `circulation_fan_high_seconds` | `20.0` | above `0` to `600` seconds | Time spent at the high circulation speed before changing back to low. |
| `bed_restore_z_height` | `30.0` | `30` to `330` mm | Bed position used while returning a temporarily raised bed to print temperature. |
| `bed_restore_side_fan_speed` | `100.0` | `0` to `100` percent | Side/auxiliary fan speed used while the bed returns to print temperature. |
| `chamber_fan_margin` | `2.0` | `0` to `10` C | Amount added to every nonzero chamber request to set the post-preparation exhaust ceiling. |
| `bed_restore_tolerance` | `5.0` | above `0` to `20` C | Allowed difference around the original bed target before M191 returns. |
| `chamber_wait_max_delta` | `5.0` | above `0` to `20` C | Upper allowance used while waiting for the chamber target. |

Invalid settings stop the macro before Klipper executes its heater, fan, or
movement commands. `M191 S0` turns off only the chamber heater and restores the
normal 35 C chamber-fan target; it preserves existing bed, hotend, model-fan,
and side-fan targets.

## Layer-time chamber commands

Creality Print may repeat `M141` when it reaches the configured chamber
activation layer. For actively heated chambers, the stock macro disables the
temperature-controlled exhaust target and can overwrite the ceiling established
by `START_PRINT` and `M191`.

The installed `k2_m141_guard` command interceptor delegates every command to
Creality's original macro handler. During an active print only, an `M141`
heating request above 40 C then restores the target to the requested chamber
temperature plus `chamber_fan_margin`. Shutdown commands such as the
end-of-print `M141 S0` are not altered, so the stock 35 C cooldown target
remains intact.

## Fluidd editor

The **Bed_Assist** macro appears in Fluidd's **Chamber Heating** category. It
opens a live editor with friendly setting names and the applicable minimum and
maximum ranges. Select a setting, choose an increment of 1, 5, or 10, and use
the Down or Up control. Bed Assist itself displays Enabled or Disabled; Down
disables it and Up enables it.

The editor also exposes **Machine Heat Soak**, the `variable_heat_soak` value
from `_START_PRINT_VARS`, in minutes. It remains a START_PRINT setting rather
than being duplicated under `_M191_VARS`; the editor simply manages both
sections in the same `custom/overrides.cfg` file.

Only the setting list scrolls. The Bed Assist title, increment selector,
Down/Up controls, Cancel, and Save & Restart remain fixed. Cancel discards the
session. Save & Restart writes only changed values to `custom/overrides.cfg`
and restarts Klipper. The editor is unavailable while printing or paused.

## Bed-assist target selection

When `bed_assist_degrees_above_commanded` is greater than zero, M191 adds it to
the original slicer-requested bed target. For example, a 70 C commanded bed and
a value of 20 C produce a 90 C assist target. When the setting is zero, M191
uses `bed_assist_bed_target` instead. Every calculated target is capped at
120 C to remain within the printer's safe bed limit.

M191 skips the entire bed-assist sequence when its calculated target is at or
below the measured bed temperature. It also never lowers a hotter bed target
already commanded by the slicer.

When assistance is needed, M191 homes when necessary, moves the bed to the
configured heating Z height, and raises the bed only when required. Both the
model and side/auxiliary fans start at the low circulation speed. They alternate
between the configured low and high speeds, using the two durations in seconds,
until the chamber reaches its target.

The circulation cycle is then disarmed and both fans stop. When M191 temporarily
raised the bed, it restores the print target, moves to `bed_restore_z_height`,
and runs only the side/auxiliary fan at `bed_restore_side_fan_speed` while the
bed returns within the configured tolerance. The side fan stops before M191
rechecks the chamber target and returns. This ensures the optional whole-machine
soak begins with both temperatures established even if bed cooling temporarily
pulled heat from the chamber. A zero original bed target does not cause an
impossible cooldown wait.

The chamber cooling-fan margin is shared with `START_PRINT`, so existing-mesh
and newly generated-mesh paths apply the same target policy. Once START_PRINT
knows the requested chamber temperature, both passive and actively heated
requests set the chamber exhaust ceiling to that temperature plus the margin.
The fan remains off below this ceiling and can immediately cool an already-hot
chamber. M191 does not silently raise or retain a higher chamber-heater target.

This macro is called by the project's `START_PRINT` workflow when the slicer
requests an actively heated chamber temperature.
