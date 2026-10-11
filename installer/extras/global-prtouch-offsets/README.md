# Global No-Carto Z Offsets

Optional, hardware-test-stage editor for the native PR Touch path. Use
**Optional extras -> Global No-Carto Z Offsets**, then power-cycle while idle
and wait for full startup. Installation also enables the tested transient-only
touchscreen compatibility; neither installation nor opening the editor moves
the printer, changes its calibration, or sends a restart. Not installed by
default. Cartographer is excluded at installation and runtime.

The `Global_Z_Offsets_No_Carto` button appears in Fluidd's Z Offsets category.
It uses a compact dialog matching the Cartographer editor: names on the left,
values on the right, increments in one row, and closer/farther side by side.
Its commands, draft session, and storage remain separate from Cartographer.
Select DEFAULT or a plate, then an increment: 0.005, 0.010, 0.025, or 0.050 mm.
**Bed up / closer** increases the value; **Bed down / farther** decreases it.
These are editing buttons, not live bed-movement commands. **Save** makes the
values persistent and active without restart; **Cancel** discards the edits.
Opening, editing, and saving are refused during printing/paused/unknown states.
The installer upgrades the shared Fluidd UI to overlay 8 while retaining the
Cartographer, Material, Bed Assist, and Creality-camera controls. Existing
installations receive migration `global-prtouch-offsets-compact-ui-v2` through
Update installer / apply updates. Refresh Fluidd after installation; complete
the protected Klippy code reload before opening the updated editor.

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

For a new offset table, DEFAULT starts at **-0.080 mm**, independently of the
native `probe.z_offset` (normally zero on a fresh stock setup). Installation
does not clear or rewrite the native calibration. An existing JSON table is
always preserved, including deliberately saved zero values and plate offsets;
updating does not reset its DEFAULT to -0.080. Deliberate edits are stored atomically in
`custom/prtouch_global_z.json`, not `printer.cfg`. That file contains a versioned
table of absolute global values. Back it up with the printer configuration.
The editor detects outside file changes and refuses to overwrite them.
Only the Save button writes this table; live taps and cleanup never do.

Migration `global-prtouch-offsets-initial-default-v3` updates this initialization
policy for installations that opted into the feature. It never edits existing
JSON values or the native calibration. For example, resetting a test native
baseline from -0.020 to zero leaves a saved global -0.025 intact; its applied
difference then becomes -0.025. Set a different saved global through the editor,
not by deleting the table or changing the native baseline.

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

Keep the PR Touch tracer enabled. Before printing, check the selected global
value and native baseline. With a fresh zero native baseline and the initial
DEFAULT of -0.080, the baseline-relative delta must be -0.080, not zero.
Existing saved tables retain their own DEFAULT. Check:

```gcode
K2_PRTOUCH_GLOBAL_Z_STATUS
K2_PRTOUCH_TOUCHSCREEN_STATUS
```

If testing a zero-delta control first, use the editor while idle to save DEFAULT
equal to the native baseline. Do not change the native calibration merely to
edit a global offset. Then change DEFAULT by just 0.005 mm. Save,
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
