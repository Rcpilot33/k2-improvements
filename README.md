# K2 Plus Improvements — Menu Installer

This fork preserves the core work from [Jacob10383/k2-improvements](https://github.com/Jacob10383/k2-improvements) and adds a guided, status-aware installer for the Creality K2 Plus.

The menu provides separate, resumable installation paths for:

- The stock PR Touch probe with no Cartographer
- A Cartographer V3 or V4 setup
- Converting a previously installed stock-probe setup to Cartographer
- Installing individual core features and optional extras
- Flashing or recovering Cartographer firmware from files bundled with this repository

## Important warnings

> [!WARNING]
> These scripts modify the printer's rooted operating system, Klipper, Moonraker, Fluidd, and printer configuration. Use them at your own risk and keep a backup of any configuration you want to preserve.

> [!CAUTION]
> After an installer, `SAVE_CONFIG`, or `FIRMWARE_RESTART` restarts Klipper, fully reboot or power-cycle the printer **before running `G28`**. A known K2 Plus motor-state issue can otherwise cause homing in the wrong direction.

These improvements are not compatible with Creality's automatic calibration workflow. Manual probe calibration, bed-mesh calibration, and tuning are recommended.

## Tested firmware and installation paths

The complete installation and printing test cycle has been performed on:

| Creality firmware | Stock probe | Cartographer | Stock probe → Cartographer | Individual features |
|---|:---:|:---:|:---:|:---:|
| `1.1.3.13` | ✓ | ✓ | ✓ | ✓ |
| `1.1.5.2` | ✓ | ✓ | ✓ | ✓ |
| `1.1.5.5` | ✓ | ✓ | ✓ | ✓ |

Testing included multiple completed prints after each installation path. Versions not listed may work, but have not received the same complete install-and-print test cycle.

Cartographer V3 and V4 normal USB/Katapult flashing and bundled STM32 DFU recovery have also been tested on printer hardware.

## Quick start

### Before you begin

1. Enable root access from the K2 Plus screen under **Settings → General → Root Account Information**.
2. Record the displayed root password and the printer's IP address.
3. Connect to the printer over SSH as `root` on port `22`. [MobaXterm](https://mobaxterm.mobatek.net/) is the recommended SSH client for Windows and includes a convenient graphical SFTP file browser.
4. Make sure no print is active.

A clean factory reset is recommended when replacing previous third-party modifications. To wipe the printer, copy this command into its SSH session:

```sh
echo "all" | /usr/bin/nc -U /var/run/wipe.sock
```

> [!WARNING]
> The wipe command is destructive. Back up the printer configuration, custom macros, saved meshes, and any other files you want to keep before running it.

After the reset, complete the on-screen setup far enough to restore the network connection, but stop before Creality calibration.

### Start bootstrap and open the installer menu

Copy this entire command into the printer's SSH session:

```sh
python3 -c 'import urllib.request; urllib.request.urlretrieve("https://raw.githubusercontent.com/Rcpilot33/k2-1155-Jacob-Fork/k2-1155-compat/bootstrap.sh", "/tmp/bootstrap.sh")' && sh /tmp/bootstrap.sh localhost --menu
```

The `--menu` path installs or updates the bootstrap requirements, then asks whether to open the installer menu. Enter `y` to continue into the menu. No, blank input, or an input failure finishes without opening it.

### Bootstrap without the menu prompt

Use this form when you only want to install or update the bootstrap and repository:

```sh
python3 -c 'import urllib.request; urllib.request.urlretrieve("https://raw.githubusercontent.com/Rcpilot33/k2-1155-Jacob-Fork/k2-1155-compat/bootstrap.sh", "/tmp/bootstrap.sh")' && sh /tmp/bootstrap.sh localhost --no-menu
```

The default with no menu flag is also `--no-menu`. On the first run, `better-root` may intentionally end the SSH session. Reconnect and start the menu with:

```sh
sh /mnt/UDISK/root/k2-improvements/menu.sh
```

Bootstrap installs Entware when needed, configures the larger persistent root home, and clones or updates this branch at `/mnt/UDISK/root/k2-improvements`.

## Choose an installation path

| Goal | Main-menu choice | What it does |
|---|---|---|
| Keep the stock PR Touch probe | **2. Install stock probe / no-Cartographer setup** | Installs the supported core stack without Cartographer. |
| Install Cartographer | **3. Install Cartographer setup** | Installs the Cartographer stack and then offers the required mount-offset picker. |
| Add Cartographer later | **3. Install Cartographer setup** | Detects and skips the components already installed by the stock-probe path. |
| Add one component | **4. Core features** or **5. Extras** | Shows installation status and runs only the selected installer. |

The installers are resumable. Before each step, the menu checks what is already installed and skips completed components. A summary reports installed, skipped, and failed steps.

The stock-probe installer does **not** remove an existing Cartographer installation or restore a converted printer automatically. It will stop if Cartographer is detected.

## Main menu

| Item | Purpose |
|---:|---|
| 1 | Show the detected printer firmware, installed setup, Cartographer hardware/firmware, offsets, core features, and extras. |
| 2 | Install the stock PR Touch / no-Cartographer setup. |
| 3 | Install the recommended Cartographer setup. Firmware flashing is intentionally separate. |
| 4 | Install individual core `k2-improvements` features. |
| 5 | Install optional features and K2 Plus patches. |
| 6 | Open normal Cartographer flashing and bundled DFU recovery tools. |
| 7 | Preview or run factory-reset cleanup tools. |
| 8 | Update the installer with a fast-forward-only `git pull`. |
| 0 | Exit. |

`[X]` means the detector considers an item installed, `[ ]` means it is not installed, and `[!]` means an extra is unavailable until its prerequisite is installed.

## Cartographer setup

### Firmware flashing

Cartographer firmware flashing is a separate, explicit menu action because it requires the probe to be connected and may require physical access.

The normal USB/Katapult path:

- Detects the connected Cartographer and its V3/V4 hardware
- Enters Katapult automatically when possible
- Offers only the firmware bundled and tested for this printer
- Writes and verifies the selected image

The included choices are:

| Hardware | Full | Lite fallback |
|---|---|---|
| Cartographer V3 / STM32F042 | `5.1.0` | `K1 5.1.0` |
| Cartographer V4 / STM32G431 | `6.0.0` | `V4 6.0.0 Lite` |

Full is the recommended K2 configuration. Lite is the conservative fallback for timing problems.

### Bundled DFU recovery

Use DFU only when normal USB/Katapult flashing cannot communicate with the probe. V3 and V4 both appear as `0483:df11` in true STM32 DFU mode, so the recovery menu requires manual hardware selection.

DFU recovery:

- Requires the probe to be placed physically into DFU mode using its pads
- Requires you to confirm V3 or V4 before writing
- Uses checksum-verified combined images bundled in this repository
- Writes both Katapult and Cartographer firmware at `0x08000000`
- Does not need an internet connection while performing the recovery

Selecting the wrong hardware image requires reflashing the correct one. Read the [Cartographer firmware instructions](./features/cartographer/firmware/README.md) before using recovery.

### Mount offsets and calibration

The Cartographer installer offers a mount-offset picker after the automatic steps. It supports the Jamin mount, JimmyV mount, and custom offsets without deleting the inherited values from `cartographer.cfg`; managed values are written to `overrides.cfg`, where they take precedence.

The offset tool retains only the two newest `overrides.cfg.before-cartographer-offset-*` backups.

After a full printer reboot, follow the [Cartographer setup and calibration guide](./features/cartographer/SETUP.md). Offsets and calibration models must match the physical mount and build surface.

## Core installation contents

The guided paths install the required items in dependency order. The Cartographer path adds Cartographer and its cleanup step; the stock-probe path omits them.

| Component | Purpose |
|---|---|
| Entware | Package toolchain used by the installers. |
| [better-root](./features/better-root/README.md) | Moves root's home to persistent UDISK storage. |
| [better-init](./features/better-init/README.md) | Loads the persistent profile environment. |
| skip-setup | Preserves Jacob's first-run wizard bypass. |
| [Moonraker](./features/moonraker/README.md) | Mainline-based Klipper API server. |
| [Fluidd](./features/fluidd/README.md) | Updated printer web interface. |
| [screws_tilt_adjust](./features/screws_tilt_adjust/README.md) | Manual bed-screw adjustment support. |
| Cartographer | Probe support and K2-specific Klipper patches; Cartographer path only. |
| abort_homing | Allows an emergency stop to abort homing. |
| Macros | Installs `START_PRINT`, `M191`, bed-mesh, and overrides support. |

Optional quality-of-life and hardware-specific changes are intentionally excluded from the guided installation paths.

## Optional extras

Extras are installed individually from menu item 5.

| Extra | Purpose / requirement |
|---|---|
| [Cartographer offset setup](./installer/extras/cartographer-offset-setup/README.md) | Select Jamin, JimmyV, or custom probe offsets; requires Cartographer. |
| [Surface selection wrapper](./installer/extras/surface-selection-wrapper/README.md) | Loads matching scan/touch models through the `START_PRINT SURFACE=` parameter; requires Cartographer. |
| [Cartographer macros](./installer/extras/cartographer-macros/README.md) | Adds `CARTO_*` calibration/load/touch-home controls; requires Cartographer. |
| [Axis twist compensation](./features/axis_twist_compensation/README.md) | Optional compensation for Z drift across X. |
| [KAMP adaptive purge](./installer/extras/kamp-adaptive-purge/README.md) | Adds the adaptive purge feature. |
| [R3MEN bed profile](./features/r3men-bed/README.md) | Adds the R3MEN graphite-bed thermistor profile. |
| [Secure Auth](./features/secure-auth/README.md) | Disables SSH password login only after a valid-looking public key is detected. Test the key in a second terminal first. |
| [PR Touch cleanup](./installer/extras/prtouch-cleanup/README.md) | Removes an orphan `[prtouch_v3]` `SAVE_CONFIG` header. |
| homing.py `hasattr` fix | Optional K2 Plus homing compatibility patch. |

## Updating

Use **8. Update installer** from the main menu, rerun either bootstrap command above, or run:

```sh
cd /mnt/UDISK/root/k2-improvements
git pull --ff-only
```

## Factory reset and cleanup

Menu item 7 provides a dry run and a separately confirmed destructive reset. Review the dry run first.

The improved reset preserves `/mnt/UDISK/root` and `/mnt/UDISK/bin`, removes most other top-level UDISK directories—including `/mnt/UDISK/printer_data`—and then triggers Creality's factory reset. Printer configuration, custom macros, saved meshes, logs, and backups under `printer_data` will be removed.

## Legacy entry points

The inherited entry-point scripts remain available for compatibility:

```sh
sh /mnt/UDISK/root/k2-improvements/gimme-the-jamin.sh
sh /mnt/UDISK/root/k2-improvements/no-carto.sh
```

The menu-based paths are recommended because they display status, skip completed work, enforce prerequisites, and provide clearer recovery instructions.

## Additional tools

Many K2 Plus beds have a pronounced valley or crown. The [`bed_leveling`](./bed_leveling) folder contains a script and guide for measuring the bed and applying aluminium tape as a shim.

See the project [FAQ](./FAQ.md) for common questions and troubleshooting.

## Project lineage and credits

This repository builds on [Jacob10383/k2-improvements](https://github.com/Jacob10383/k2-improvements). The menu-based installer work was informed by [erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24) and other community forks while keeping Jacob's feature installers and project layout recognizable.

Original-project acknowledgements:

- [@Guilouz](https://github.com/Guilouz)
- [@stranula](https://github.com/stranula)
- [@juliosueiras](https://github.com/juliosueiras)
- [Moonraker](https://github.com/Arksine/moonraker)
- [Klipper](https://github.com/Klipper3d/klipper)
- [Fluidd](https://github.com/fluidd-core/fluidd)
- [Entware](https://github.com/Entware/Entware)
- [Cartographer 3D](https://github.com/Cartographer3D)

Donations to support Jacob's original work are available through [Jacob10383's Ko-fi](https://ko-fi.com/jacob10383).

## Disclaimer

Use this software at your own risk. The maintainers and contributors are not responsible for damage to the printer, probe, configuration, or other property.
