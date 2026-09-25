# K2 Plus Macro Bundle

Installs the four macro components used by both guided setup paths:

- [`START_PRINT`](./start_print/README.md)
- [`M191`](./m191/README.md)
- [temperature-aware bed mesh macros](./bed_mesh/README.md)
- `custom/overrides.cfg`

The overrides file is created only when missing. Re-running the installer
preserves existing mount selections and user changes. New files seed the PLA,
PETG, ABS, ASA, and default offsets at `0`, along with a zero-minute heat soak.
Obsolete installer-managed entries are removed during updates; firmware
compatibility state is kept in managed files rather than exposed as a user
setting.

The installer also adds any missing `_M191_VARS` defaults without replacing
existing selections. These settings control bed assistance, heating and return
Z positions, alternating low/high circulation speeds and timers, bed-return
side-fan cooling, chamber-fan margin, and wait tolerances. See the
[M191 documentation](./m191/README.md) for ranges and exact behavior.

The separate `variable_bed_mesh_soak` setting defaults to five minutes and is
used only when the stock-probe workflow must create a missing saved mesh. Users
who heat soak before sending a print can set it to `0`.

The same overrides template serves both setup paths. When Cartographer is
present, its installer adds active `[cartographer touch]` and
`[cartographer scan]` sections. They contain the Touch noisy-sample limit and
the scan-run/path choices. Those Cartographer-only sections are absent from a
stock PR Touch installation, and existing user-selected values are preserved
on reinstall.

M191 is part of the core macro bundle, so its `_M191_VARS` settings are present
in the shared overrides template. KAMP remains an optional extra: the core
installer and Cartographer settings organizer never create `_KAMP_Settings`.
When KAMP is installed, its installer creates that section and the organizer
keeps it after the M191 settings without replacing user-selected values.

On firmware `1.1.3.13`, installation also enables a compatibility definition
for the missing `SET_TEMPERATURE_FAN_SWITCH` command still called by Creality's
stock macros. It is a no-op because those macros already set the chamber-fan
target and pin directly. The definition is disabled on all other firmware.

Each macro is included from `custom/main.cfg`. The combined installer performs
one protected restart after all four components are installed and waits for K2
motor initialization before returning. A Klippy host-process reload is used
when the stock PR Touch pre-XY clearance guard is installed or refreshed. The
guard is armed only when `SAFE_MOVE_Z` begins from Creality's artificial Z
reference, then consumed by its first following `_HOME_Z`, so ordinary inter-
print moves and later Z-home passes do not repeat the retreat.
