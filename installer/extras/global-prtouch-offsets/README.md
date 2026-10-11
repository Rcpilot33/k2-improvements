# Global No-Carto Z Offsets

Optional, hardware-test-stage editor for the native PR Touch path. Use
**Optional extras -> Global No-Carto Z Offsets**, then power-cycle while idle
and wait for full startup. Installation also enables the tested transient-only
touchscreen compatibility; neither installation nor opening the editor moves
the printer, changes its calibration, or sends a restart. Not installed by
default. Cartographer is excluded at installation and runtime.

The `Global_Z_Offsets_No_Carto` button appears in Fluidd's Z Offsets category.
It uses Fluidd's standard prompt dialog, not a replacement web build. Select
DEFAULT or a plate, then an increment: 0.005, 0.010, 0.025, or 0.050 mm.
**Bed up / closer** increases the value; **Bed down / farther** decreases it.
These are editing buttons, not live bed-movement commands. **Save** makes the
values persistent and active without restart; **Cancel** discards the edits.
Opening, editing, and saving are refused during printing/paused/unknown states.

## Selection and storage

- Without plate-aware saved meshes installed, only DEFAULT is used/shown.
- With that workflow installed, `START_PRINT SURFACE=<name>` uses its global
  offset; omitted/empty `SURFACE` or `SURFACE=default` uses DEFAULT.
- A plate without an explicit value inherits DEFAULT, not zero. **Use DEFAULT**
  removes an explicit override. A changed DEFAULT updates inherited plates.
- Each new print resets the previous plate selection before preparation and
  applies the supplied selection after native homing/meshing.
- The existing Creality Print and Orca surface templates are reused unchanged.
  `high_temp` and `textured_pei` are shared names; `epoxy`, `custom`, and Orca's
  distinct names remain separate. Custom names from saved mesh profiles or
  previously saved entries are also shown. Values are per surface, not per
  bed/chamber temperature. A slicer plate type is not a unique physical sheet;
  use unique SURFACE names for separate sheets of the same type.

Before the first explicit save, DEFAULT equals the existing native
`probe.z_offset` exactly (e.g. -0.020); installation does not migrate, clear,
or rewrite it. Deliberate edits are stored atomically in
`custom/prtouch_global_z.json`, not `printer.cfg`. That file contains a versioned
table of absolute global values. Back it up with the printer configuration.
The editor detects outside file changes and refuses to overwrite them.
Only the Save button writes this table; live taps and cleanup never do.

Creality's native saved `[prtouch_v3] z_offset` remains the baseline. A chained
G-code move transform applies only `selected_global - native_baseline`, leaving
the existing mesh transform in place. A larger global value moves the bed
closer on subsequent moves; a smaller value moves it farther. This avoids
patching the compiled PR Touch driver or applying the loaded baseline twice.
It does not alter homing, `probe.z_offset`, material variables,
`gcode_move.homing_origin`, or the touchscreen status contract. Both displays
continue showing only material plus live adjustment. Native direct homing
moves bypass the transform and retain their existing behavior.

Native `Z_OFFSET_APPLY_PROBE` bookkeeping/recovery continues unchanged. If the
native print-recovery JSON file exists, the selected surface/value/baseline is
recorded in a separate field, preserving every existing field. Native homing's
position synchronization restores that frozen value, not a later table edit.
If recovery attempts a move before synchronizing a changed offset, motion is
refused. A changed native baseline or a removed plate workflow also blocks
that recovery rather than guessing. This
additional power-loss path has unit tests but still needs physical validation.

## Initial hardware test

Keep the PR Touch tracer enabled. First use the inherited DEFAULT unchanged:
the baseline-relative delta must be zero and the existing adjusted completion /
cancellation behavior must stay unchanged. Check:

```gcode
K2_PRTOUCH_GLOBAL_Z_STATUS
K2_PRTOUCH_TOUCHSCREEN_STATUS
```

Then, while idle, open the editor and change DEFAULT by just 0.005 mm. Save,
run the same small print, and compare its first layer while ready to cancel.
Verify the console reports the expected global/baseline/delta and neither
display adds global to the material value. Live-adjust and finish/cancel;
verify live Z returns to zero and no native calibration is staged. Power-cycle
idle and verify the deliberate DEFAULT edit persisted. Restore the original
value through the editor if desired.

After installing plate-aware meshes, test two distinct plate values, then a
print without SURFACE to verify DEFAULT, and an unconfigured/custom surface to
verify inheritance. Test both slicer template families. No claim of hardware
validation is made until those checks pass; keep initial changes tiny.

Manual install/remove (idle only):

```sh
sh installer/extras/global-prtouch-offsets/install.sh
sh installer/extras/global-prtouch-offsets/install.sh --remove
```

Removal preserves the JSON table, required touchscreen compatibility, and
managed START_PRINT. Power-cycle to unload the transform; without the feature,
printing uses the original native baseline again. Existing unrelated pending
SAVE_CONFIG values are never cleared or saved by this editor.
