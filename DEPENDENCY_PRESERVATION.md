# Dependency Preservation Record

This file records fallback copies of external repositories used by K2
Improvements. The table below records the original preservation snapshot.
Moonraker and Fluidd still use their original sources. The Cartographer
testing exception is described next.

## Cartographer integration testing

On `carto-plugin-update-testing`, the installer and Moonraker both use
`Rcpilot33/cartographer3d-plugin`, branch `k2-cartographer-upstream-integration`
(reviewed baseline `213504f`). This is a moving testing branch, not a commit pin.
Re-run the Cartographer installer after switching K2 Improvements to this branch;
updating K2 Improvements alone does not migrate the installed plugin checkout.
The installer accepts a clean, fast-forward migration from Jacob's fork and
refuses local changes, unknown origins, and divergent history. Existing local
branches are retained. The installed plugin directory and import shim stay the
same; USB bridge, K2 patches, touchscreen compatibility, and firmware are unchanged.
The normal installer ends with its existing Klipper code restart; run it only
while idle. No MCU firmware flash is part of this change.

Before promotion, validate disconnected startup, reconnect, guarded homing,
repeated meshes, and print start/cancel on hardware using the plugin's
`K2_UPSTREAM_INTEGRATION.md` checklist. Do not reset the checkout to roll back:
preserve it first and deliberately restore the previous plugin source and matching
Moonraker configuration while idle.

### Reconnect and installer follow-up

The K2 MCU patch now emits a per-MCU identification event before reconnect
configuration is built. The MCU temperature sensor initializes on that event,
so a probe absent at startup gets ADC sampling configured when it connects.
Initialization failures abort the reconnect rather than reporting success.
The existing post-configuration reconnect event used by the plugin is unchanged.

The updater offers a Cartographer refresh for this change. After a successful
install/restart, Cartographer's bundled SAVE_CONFIG and upload-guard migrations
are recorded only if their installed-state detectors pass. Missing protections
remain pending. No calibration values or temperature conversion formulas change.

Both native and portable Jacob-overlay installs now carry the matching MCU and
temperature_mcu patches. The fix concerns MCU ADC temperature initialization;
coil streaming is a separate path. Overlay parity and repeat application are
covered by local tests; this is not a claim of end-to-end overlay printer validation.
Feature/Extras menus explicitly report incomplete migration verification after
an otherwise successful install, leaving failed dependency actions pending.

### Release gate and branch transitions

The integration branch is a moving TEST target, not a release channel. Do not
promote this installer configuration to main until a release-only plugin branch
and its tested commit are selected. Publish/verify that branch first, update the
native and overlay update-manager configurations together, and ship a refresh
migration that re-runs the installer and protected host restart. Do not rely on
a configuration-only pull to activate new plugin Python code.

Fresh and migrated plugin checkouts fetch all origin branches, while tracking
only the configured primary branch for updates. This avoids hiding a later
release branch behind a single-branch refspec; it does not automatically migrate
existing printers until they run the updated installer. Confirm Moonraker reports
the component valid, on the intended branch, after that migration.

### V3 hardware validation, September 19–20, 2026

User-supplied logs and supervised observations on K2 Plus 1.1.5.5, Cartographer
V3 firmware 5.1.0, plugin integration through 5ed2ee7:

- Passed disconnected startup, idle reconnect, live MCU/coil temperature
  recovery, and automatic removal of the stale startup warning after reconnect.
- Passed Scan/Touch calibration, protected SAVE_CONFIG restart, subsequent model
  loading, normal homing, Z tilt, and repeated meshes.
- Passed disconnect/reconnect during ordinary printing: Fluidd 23:07:16 to
  23:07:32, followed by successful print completion. This did not test active
  probing disconnection.
- Passed next-print homing, meshing, Touch home and completion without a Klipper
  restart. Passed normal cancellation/parking/heater shutdown (user observation),
  followed by another successful print ending 23:35:17 without a restart.
- V3 directional mesh striping predates this update. It follows scan direction;
  repeated spiral meshes reduce it. Root cause and absolute accuracy remain
  unestablished; do not label it an update regression or claim spiral fixes it.

Still pending: supervised disconnected-operation rejection, full power-cycle
persistence, broad heated first-layer/longer-print validation, Moonraker update
manager health, and a real pre-migration/portable-overlay printer install.
Local Git fixtures exercise both Jacob origin spellings, fast-forward migration,
tracking repair, future-branch visibility, and refusal to overwrite user changes.
They do not substitute for those remaining printer checks. No firmware flash or
deliberate disconnection during an active probe move is required.

Preservation date: **2026-08-16**

## Preserved repositories

| Component | Current source | Preserved public fork | Installer ref | Commit | Tree |
|---|---|---|---|---|---|
| Moonraker | [`Jacob10383/moonraker`](https://github.com/Jacob10383/moonraker) | [`Rcpilot33/moonraker`](https://github.com/Rcpilot33/moonraker) | `k2` | `70685677006ac3becd123650db3e60cd1eb56f88` | `8d065300303858c001c7deb554219d927859bf14` |
| Fluidd | [`Jacob10383/fluidd`](https://github.com/Jacob10383/fluidd) | [`Rcpilot33/fluidd`](https://github.com/Rcpilot33/fluidd) | release `v1.37.4` | `d7c08e148925dbec0b88ef435b65581b7d583847` | `7d07c3a70d96c9300fba8f62dacebe62ad136d88` |
| Cartographer plugin | [`Jacob10383/cartographer3d-plugin`](https://github.com/Jacob10383/cartographer3d-plugin) | [`Rcpilot33/cartographer3d-plugin`](https://github.com/Rcpilot33/cartographer3d-plugin) | `main` | `3b895c7994a71097deefb545a4e473d5c99486c3` | `5d9d342948449a0013ffbbf30f96851328ced8c2` |

The Fluidd `develop` branch also pointed to
`d7c08e148925dbec0b88ef435b65581b7d583847` when this record was created.

## Fluidd release asset

The installer downloads the latest GitHub release asset rather than building
Fluidd from its Git repository. The active release was therefore copied to a
matching public release in the preserved fork.

| Field | Value |
|---|---|
| Original release | [`Jacob10383/fluidd` `v1.37.4`](https://github.com/Jacob10383/fluidd/releases/tag/v1.37.4) |
| Preserved release | [`Rcpilot33/fluidd` `v1.37.4`](https://github.com/Rcpilot33/fluidd/releases/tag/v1.37.4) |
| Asset | `fluidd.zip` |
| Size | `4,317,984` bytes |
| SHA-256 | `5f2d716ceb5d7a62a784436608728e5aacfe87cb7b1a30ab386f6089206ca6fa` |

The original and preserved assets were downloaded independently after the
preserved release was published. Their byte counts and SHA-256 hashes match.

## Verification results

Fork creation used GitHub's **copy all branches** option. `git ls-remote` was
then run independently against each current source and preserved fork.

| Repository | Branches | Tags | Branch ref differences | Tag ref differences |
|---|---:|---:|---:|---:|
| Moonraker | 4 | 23 | 0 | 0 |
| Fluidd | 7 | 126 | 0 | 0 |
| Cartographer plugin | 7 | 93 | 0 | 0 |

Annotated tags produce both tag and peeled-tag lines in `git ls-remote`; the
comparison included all of those returned refs. The recorded commit and tree
IDs provide an immutable content check for the refs used by the installer.

## Future activation checklist

Do not switch the installer merely because these copies exist. Before making
them active sources:

1. Recheck the source and preserved refs for any intentional upstream changes.
2. Pin the installation sources to the specifically tested commits or release.
3. Change the installer and corresponding update-manager origins together.
4. Test fresh no-Cartographer and Cartographer installations on supported K2
   Plus firmware.
5. Test update-manager behavior and a Fluidd reinstall from the preserved
   release.
6. Update installation, recovery, and dependency documentation only after the
   complete hardware validation passes.
