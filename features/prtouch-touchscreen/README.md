# Native PR Touch touchscreen Z-offset compatibility

Opt-in **no-Cartographer** compatibility for the 1.1.5.5 native `[prtouch_v3]`
setup. This is not the global-offset editor and
is not automatically installed by setup, the menu, or update migrations.
Cartographer's existing compatibility module and installers are unchanged.

## Why this is needed

Creality's master-server reads `probe.z_offset` for the touchscreen and uses
that value in its cleanup pair:

```gcode
SET_GCODE_OFFSET Z_ADJUST=<reported probe.z_offset> MOVE=0
Z_OFFSET_APPLY_PROBE
```

Native `PrinterProbe.get_status()` normally reports its loaded or staged
calibration. With a loaded calibration of -0.020, material offset +0.100,
and live adjustment +0.005, the native handler stages -0.125. Master-server
then subtracts 0.125 from a live offset of +0.105, leaving -0.020 and staging
zero. Both printers' logs confirm that master-server issues the same command
pair; the meaning of the reported status field differs.

This module instead reports **inverse live G-code Z offset** in that one
status field, following the existing Cartographer compatibility contract.
The same example then reports -0.105 to the client; cleanup returns live Z to
zero. This display/cleanup behavior passed adjusted, unadjusted, and cancelled
hardware prints on the no-Carto 1.1.5.5 test printer.

The new **transient-only** version also replaces the registered no-Carto
`Z_OFFSET_APPLY_PROBE` handler. It performs the same in-memory bookkeeping and
calls the native print-recovery recorder, but never calls `configfile.set()`
or prints a SAVE_CONFIG prompt. Thus neither a live adjustment nor cleanup
stages any native calibration, even when cleanup restores the original number.
This applies to all calls of that command while this feature is active;
there is no staging parameter or legacy alias. The dedicated global-offset
editor is the next feature and will own the deliberate save path.

Existing pending values are not cleared or overwritten, and other intentional
calibration/configuration saves still work. Do not mistake an old pending value
from an earlier print for a new write by this version. A fresh idle power-cycle
without saving clears old pending state before the test.

The module does not change `probe.z_offset`, `get_offsets()`, the native driver,
homing/motion handlers, material macros, or stored calibration. It sends no
G-code and does not patch `configfile.set()` or SAVE_CONFIG. It stays inactive
whenever `cartographer` is loaded, even
if a dummy `prtouch_v3` object exists, and requires a native probe named
`prtouch_v3`. All other probe status fields are preserved.

Expected displays: zero while idle after startup, then the material offset
when START_PRINT applies it, updated by live adjustment. Unlike the old native
display, the touchscreen should agree with Fluidd before the first live tap.
This changes what consumers see in `probe.get_status()['z_offset']`; consumers
needing the true calibration must use the native calibration attributes or
the separate diagnostic status below, not the display field.

## Install / remove

On the **no-Carto printer only**, finish or cancel any print first:

```sh
cd ~/k2-improvements
sh features/prtouch-touchscreen/install.sh
```

The installer queries local Moonraker (five-second timeout), requires an idle
native configuration, and refuses printing, paused, unknown, or Cartographer
states. It links its module/config and enables only its own include in existing
`custom/main.cfg`. It refuses unfamiliar files or links and does not edit
`printer.cfg`, restart, or change offsets. `KLIPPER_DIR`, `PRINTER_CFG_DIR`,
`K2_PYTHON`, and `MOONRAKER_URL` can override the default paths/runtime/endpoint.
No SSH credentials, keys, or printer IP are embedded in the feature.

Power-cycle while idle **without saving an old test's pending calibration**,
then wait for complete K2 startup. New Python code requires a fresh Klippy
process. Run in Fluidd:

```gcode
K2_PRTOUCH_TOUCHSCREEN_STATUS
```

Expect `installed=True`, `transient_only=True`, `live_z_offset=0`,
`probe_z_offset=0`, and your
existing `loaded_z_offset` (currently -0.020 on the test printer).
`native_reported_z_offset` shows the underlying loaded/in-memory bookkeeping
value, separate from the inverse-live value sent to the factory client. During
live adjustment that bookkeeping value is not staged for saving.

Remove while idle, then power-cycle to unload:

```sh
sh features/prtouch-touchscreen/install.sh --remove
```

Only its include and owned symlinks are disabled/removed. This does not restore
calibration or undo any SAVE_CONFIG performed by the user.

## Transient-only hardware test

Keep the existing PR Touch tracer installed. Do not change calibration or
material offsets for this test, and do not SAVE_CONFIG during it.

1. After startup, capture the compatibility status and
   `K2_PRTOUCH_Z_TRACE_SNAPSHOT LABEL=compat_before_print`.
2. Start the same small known print. Confirm both displays agree once the
   material offset is applied. Watch the first layer; stop if clearance is wrong.
3. Before/after one small normal touchscreen adjustment, capture snapshots
   labeled `compat_before_adjust` / `compat_after_adjust` and compatibility
   status. Note the display values. Do not send an extra console adjustment.
4. During live adjustment and after completion, verify **no** `[prtouch_v3]
   `z_offset` is pending for SAVE_CONFIG and no SAVE_CONFIG prompt is emitted
   by offset apply. Capture compatibility status and a snapshot labeled
   `compat_after_print`. Expected live offset after completion: zero. Loaded
   calibration stays unchanged; in-memory bookkeeping returns to that value.
5. Collect `prtouch-z-trace.log`, `klippy.log`, and master-server logs before
   restarting. Then repeat an unadjusted print; test cancellation separately
   while watching the printer before promoting this to automatic installation.

With this feature, the tracer's `probe_reported_offset` is the inverse-live
display field, **not** staged calibration. `probe_calibrate_offset` and
`probe_change_flag` also change for native print-recovery bookkeeping, without
staging a save. Use `pending_save_offset` to identify actual pending calibration,
and `probe_loaded_offset` / file entries for loaded / saved values.
There should be no `config_set_before/after` events for native z_offset from
live adjustment or cleanup. The native compiled driver's physical use
of calibration is not proven by status alone; local tests cover the Python
status/cleanup contract, not hardware motion.
