# Dependency Preservation Record

This file records fallback copies of external repositories used by K2
Improvements. These copies are preserved for continuity only. The installer
and Moonraker update-manager configurations still use their existing sources;
none of the `Rcpilot33` copies below are active installation sources.

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
