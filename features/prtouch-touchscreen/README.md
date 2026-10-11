# Native PR Touch touchscreen Z-offset compatibility

Opt-in **no-Cartographer** compatibility for the first hardware test on the
1.1.5.5 native `[prtouch_v3]` setup. This is not the global-offset editor and
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
zero and the unmodified native handler stages the original -0.020 calibration.
The temporary combined calibration can still be staged during live adjustment.
Staging is not an on-disk save; do not save a temporary combined value mid-print.

The module does not change `probe.z_offset`, `get_offsets()`, the native driver,
homing/motion/offset command handlers, material macros, or stored calibration.
It sends no G-code. It stays inactive whenever `cartographer` is loaded, even
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

Power-cycle while idle **without saving the previous test's pending zero**,
then wait for complete K2 startup. New Python code requires a fresh Klippy
process. Run in Fluidd:

```gcode
K2_PRTOUCH_TOUCHSCREEN_STATUS
```

Expect `installed=True`, `live_z_offset=0`, `probe_z_offset=0`, and your
existing `loaded_z_offset` (currently -0.020 on the test printer).
`native_reported_z_offset` shows the underlying loaded/staged calibration,
separate from the inverse-live value sent to the factory client.

Remove while idle, then power-cycle to unload:

```sh
sh features/prtouch-touchscreen/install.sh --remove
```

Only its include and owned symlinks are disabled/removed. This does not restore
calibration or undo any SAVE_CONFIG performed by the user.

## First hardware test

Keep the existing PR Touch tracer installed. Do not change calibration or
material offsets for this test, and do not SAVE_CONFIG during it.

1. After startup, capture the compatibility status and
   `K2_PRTOUCH_Z_TRACE_SNAPSHOT LABEL=compat_before_print`.
2. Start the same small known print. Confirm both displays agree once the
   material offset is applied. Watch the first layer; stop if clearance is wrong.
3. Before/after one small normal touchscreen adjustment, capture snapshots
   labeled `compat_before_adjust` / `compat_after_adjust` and compatibility
   status. Note the display values. Do not send an extra console adjustment.
4. After completion, capture compatibility status and a snapshot labeled
   `compat_after_print`. Expected live offset: zero. Expected pending native
   calibration: the original loaded value, not zero or a combined value.
5. Collect `prtouch-z-trace.log`, `klippy.log`, and master-server logs before
   restarting. Then repeat an unadjusted print; test cancellation separately
   while watching the printer before promoting this to automatic installation.

With this feature, the tracer's `probe_reported_offset` is the inverse-live
display field, **not** staged calibration. Use `probe_loaded_offset`,
`probe_calibrate_offset`, `pending_save_offset`, and file entries to distinguish
loaded, staged, and saved values. The native compiled driver's physical use
of calibration is not proven by status alone; local tests cover the Python
status/cleanup contract, not hardware motion.
