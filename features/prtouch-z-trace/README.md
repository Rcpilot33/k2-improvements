# Temporary native PR Touch Z-offset trace

Opt-in diagnostics for a no-Cartographer K2 using `[prtouch_v3]`. This is **not
the global Z-offset editor** and is not installed by the menu or migrations.
It observes Creality's existing behavior; it does not send motion, reset an
offset, save configuration, or automatically restart the printer.

## Install on the no-Carto test printer

Use the repository checkout on the **1.1.5.5 / 192.168.1.103** test printer.
Finish or cancel any print first; paused and unknown states are refused.

```sh
cd ~/k2-improvements
sh features/prtouch-z-trace/install.sh
```

This links the diagnostic module into `~/klipper/klippy/extras`, links its
config into `printer_data/config/custom`, and enables its own include in
`custom/main.cfg`. It refuses to overwrite unfamiliar files/links. Set
`KLIPPER_DIR` or `PRINTER_CFG_DIR` if those paths differ on your printer.
`printer.cfg`, saved calibrations, and other features are untouched.

Power-cycle while idle and wait for full K2 startup. The helper needs a fresh
Klippy process. Do not home or print while startup is incomplete.

## Controlled test

Keep a backup of `printer.cfg` before any **manual** calibration edit. Start
with a known safe calibration value, not a large experimental displacement.
The tracer never changes that value for you. Run one test at a time:

1. After startup, run `K2_PRTOUCH_Z_TRACE_SNAPSHOT LABEL=before_home`.
2. Home normally, then run `K2_PRTOUCH_Z_TRACE_SNAPSHOT LABEL=after_home`.
3. Start the same small, known print through the usual stock workflow, with
   the same leveling/AI settings as when you saw the reset. Watch the first
   layer and stop if clearance is wrong.
4. After completion/cancellation, run
   `K2_PRTOUCH_Z_TRACE_SNAPSHOT LABEL=after_print`.
5. Download the trace and `klippy.log` **before** restarting. After a normal
   idle restart/power-cycle, run
   `K2_PRTOUCH_Z_TRACE_SNAPSHOT LABEL=after_restart` and collect the new logs.

To reproduce your original observation, repeat after your existing safe
manual edit/restart procedure. Don't use `SAVE_CONFIG` just to produce a trace:
it may persist other pending calibration changes. A stock-only setup lacking
this repository's `custom/main.cfg` cannot use this installer; don't install
the full macro suite just for the test. Such a setup needs a separately
reviewed diagnostic include placement to preserve its stock workflow.

## What to collect / interpret

Default output is `printer_data/logs/prtouch-z-trace.log`, JSON per line,
with two rotating backups (`.1`, `.2`), each bounded to roughly 1 MiB. Collect
all three if present. The log persists through restart and includes UTC,
monotonic time, process ID, command nesting, and sequence numbers.

It separates:

- `file.entries.normal` and `file.entries.save_config`: values actually in
  `printer.cfg`, including a change made outside Klipper's config writer.
- `loaded_config_offset`: the effective config value read by this session.
- `probe_loaded_offset`: the probe's `z_offset` attribute.
- `probe_reported_offset`, `probe_calibrate_offset`, `probe_change_flag`:
  pending calibration vs the originally loaded value.
- `pending_save_offset`: a value staged for the next config save.
- `homing_origin_z`: the live G-code offset shown by Fluidd, **not** necessarily
  the native probe calibration.
- `native_fields`: a few scalar wrapper fields, if exposed by this firmware;
  `null` means unavailable, not zero.

If the opt-in [native touchscreen compatibility](../prtouch-touchscreen/README.md)
is installed, `probe_reported_offset` instead represents inverse live adjustment
for the factory display/cleanup contract. Use `probe_calibrate_offset` and
`pending_save_offset` for staged calibration; `probe_loaded_offset` and file
entries still identify loaded/saved calibration. The tracer itself is unchanged.

`config_set_before` records the requested `[prtouch_v3] z_offset` and Python
caller stack. `config_set_after` shows resulting staged state. Commands such
as homing, preparation, offset application, restore-state, config save, and
print finish are recorded before/after; the original handler runs exactly
once. `command_error` preserves the original failure. `state_changed` samples
other changes once per second; it cannot identify an outside writer's caller
or changes that happen and revert entirely between samples. File timestamps
can miss same-size external rewrites on coarse filesystems; command snapshots
force a reread. Native C internals aren't exposed, so this is evidence of
visible transitions, not a claim to trace every internal computation.

Temperatures and mesh profile are context, not continuous log triggers. No
extra process is started. Small synchronous diagnostic writes can add some
overhead; this is temporary test instrumentation, not a permanent feature.
If logging fails, diagnostics must not prevent a native command from running;
look for `PR Touch Z trace could not record` in `klippy.log`. Do not assume a
zero live origin proves that the probe calibration was lost or applied twice.

## Remove

While idle, from the same checkout:

```sh
sh features/prtouch-z-trace/install.sh --remove
```

This disables only its include and removes only its two owned symlinks.
Logs are retained. Power-cycle while idle to unload the diagnostic hooks.
No calibration is restored or reset, because the helper never changed it.
