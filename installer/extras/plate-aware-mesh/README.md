# Plate-Aware Saved Meshes

This optional extra keeps separate saved bed meshes for different build
plates on a K2 Plus using the stock PR Touch probe.

## Naming

When `START_PRINT` receives a `SURFACE` parameter, the surface is added before
the existing bed- and chamber-temperature name:

| `START_PRINT` parameters | Saved mesh profile |
|---|---|
| `BED_TEMP=70 CHAMBER_TEMP=0 SURFACE=textured_pei` | `textured_pei_70.0c_0.0c` |
| `BED_TEMP=70 CHAMBER_TEMP=0 SURFACE=high_temp` | `high_temp_70.0c_0.0c` |
| `BED_TEMP=70 CHAMBER_TEMP=0` | `70.0c_0.0c` |

Omitting `SURFACE` deliberately preserves the original temperature-only
behavior. Existing profiles therefore remain usable, and slicer profiles can
be converted one at a time.

## Slicer setup

Use one of the complete Creality Print plate-selection templates in
[`slicer-templates`](../kamp-adaptive-purge/slicer-templates/README.md). They
map Creality Print's four build-plate choices to these stable names:

| Creality Print bed type | `SURFACE` |
|---|---|
| Epoxy Resin Plate | `epoxy` |
| High Temp Plate | `high_temp` |
| Textured PEI Plate | `textured_pei` |
| Customized Plate | `custom` |

Use lowercase letters, numbers, and underscores in manually supplied surface
names. Do not include spaces.

The slicer value identifies a plate type, not a physical sheet. If you own two
plates of the same type and want separate meshes, create separate slicer
profiles that pass unique names such as `textured_pei_a` and
`textured_pei_b`. The selected slicer profile must always match the plate
actually installed on the printer.

## Scope and behavior

- Stock PR Touch/no-Cartographer installations only.
- A missing plate-and-temperature profile is created by the existing
  `MESH_IF_NEEDED` workflow.
- A matching saved profile is reused.
- The existing bed temperature, chamber temperature, heat soak, nozzle clean,
  and mesh calibration sequence is unchanged.
- Cartographer continues creating its adaptive mesh and is not affected.

When a profile is created for the first time, finish or cancel the print
safely and then use **Save Config & Restart** to persist it in `printer.cfg`.
Wait for the protected firmware restart to complete before the next `G28`.

The additional soak used only when creating a missing profile is controlled in
`custom/overrides.cfg`:

```ini
variable_bed_mesh_soak: 5
```

Set it to `0` if the printer is already heat soaked before you send a print.
The plate-aware installer adds the five-minute default to older preserved
overrides files when it is missing; it does not change an existing value.

Changing or reseating a plate can still change its measured shape. If a saved
profile no longer represents the installed plate, remove that profile and let
the next print recreate it. A fresh mesh every print remains the most
conservative option; this feature trades that extra probing time for named
per-plate reuse.

## Installation and verification

From the main installer, select **Optional extras -> Plate-aware saved
meshes**. The installer adds one marker config and performs a firmware restart.

Before moving the printer, preview both naming paths in the Fluidd console:

```gcode
PLATE_AWARE_MESH_STATUS SURFACE=textured_pei BED_TEMP=70 CHAMBER_TEMP=0
PLATE_AWARE_MESH_STATUS BED_TEMP=70 CHAMBER_TEMP=0
```

The expected resolved profiles are `textured_pei_70.0c_0.0c` and
`70.0c_0.0c` respectively.

For the first test, temporarily use a `3,3` probe count, select a plate in the
slicer, and verify the console reports a name such as:

```text
Looking for textured_pei_70.0c_0.0c ...
Loading bed mesh: textured_pei_70.0c_0.0c...
```

Then repeat without `SURFACE=` and confirm it reports the original
`70.0c_0.0c` format. Restore the normal `19,19` probe count after testing.
