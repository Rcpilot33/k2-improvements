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

Before the current menu and bootstrap redesign, the complete installation and
printing test cycle was performed on:

| Creality firmware | Stock probe | Cartographer | Stock probe → Cartographer | Individual features |
|---|:---:|:---:|:---:|:---:|
| `1.1.3.13` | ✓ | ✓ | ✓ | ✓ |
| `1.1.5.2` | ✓ | ✓ | ✓ | ✓ |
| `1.1.5.5` | ✓ | ✓ | ✓ | ✓ |

That baseline testing included multiple completed prints after each installation
path. The redesigned menu and bootstrap are now being revalidated separately:

| Creality firmware | Current menu/bootstrap revalidation |
|---|:---:|
| `1.1.5.5` | **PASS** |
| `1.1.3.13` | Pending retest |
| `1.1.5.2` | Pending retest |

The current `1.1.5.5` cycle passed the stock PR Touch path, both Cartographer
installation paths, feature and detector checks, all four Creality Print
templates, and the complete Cartographer surface-profile workflow. See the
[validation report](./VALIDATION.md) for the tested matrix and exact
selector/action sequence. Versions not listed may work, but have not received
the same complete install-and-print test cycle.

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

After the reset, complete the full on-screen Creality setup and its factory
calibrations, including cutter calibration and input shaping. Restore the
network connection and finish that setup before starting bootstrap. Once these
modifications are installed, use the provided manual calibration workflows
instead of rerunning Creality's automatic calibration.

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

### If installing Cartographer, prepare its hardware first

If you are keeping the stock PR Touch probe, skip this section and continue to
**Choose an installation path**, then select the stock PR Touch path.

Complete the stock Creality setup and factory calibrations first. Then power
off the printer and physically install the correct Cartographer mount, any
spacers required by that mount, its wiring, and its USB connection. Confirm
whether the connected probe is Cartographer V3 or V4.

After bootstrap opens the installer, review **Cartographer tools -> Firmware
flash** before selecting the Cartographer installation path. Use only the
bundled, tested firmware matching the connected hardware. Normal USB/Katapult
flashing is preferred; use DFU recovery only when normal flashing cannot
communicate with the probe.

Selecting the wrong mount preset, omitting required spacers, or flashing
firmware for the wrong hardware can produce incorrect probe positioning or
leave the probe unavailable.

## Choose an installation path

| Goal | Menu path | What it does |
|---|---|---|
| Keep the stock PR Touch probe | **Install or change setup -> Stock probe** | Installs the supported core stack without Cartographer. |
| Install Cartographer | **Install or change setup -> Cartographer setup** | Installs the Cartographer stack and then offers the required mount-offset picker. |
| Add Cartographer later | **Install or change setup -> Convert stock setup to Cartographer** | Detects and skips components already installed by the stock-probe path. |
| Add one optional extra | **Optional extras** | Shows its current state and runs only the selected installer. |
| Repair one core component | **Maintenance and recovery -> Core component installer** | Opens the advanced individual-component menu. |

The installers are resumable. Before each step, the menu checks what is already installed and skips completed components. A summary reports installed, skipped, and failed steps.

The stock-probe installer does **not** remove an existing Cartographer installation or restore a converted printer automatically. It will stop if Cartographer is detected.

## Main menu

| Item | Purpose |
|---:|---|
| 1 | Show the detailed installation, firmware, Cartographer, component, and extras status. |
| 2 | Install, repair, or change the printer setup path. |
| 3 | Open Cartographer firmware, DFU recovery, mount-offset, and calibration tools. |
| 4 | Install optional hardware, print-workflow, and security extras. |
| 5 | Open individual component repair, PR Touch cleanup, and factory-reset tools. |
| 6 | Update the installer with a fast-forward-only `git pull`, then reload the menu. |
| 0 | Exit. |

Menu states are written as colored words rather than checkboxes: green
`INSTALLED`/`COMPLETE`, gray `NOT INSTALLED`/`AVAILABLE`, yellow
`REQUIRES ...`/`INCOMPLETE`/`RECOVERY`, and red `DESTRUCTIVE`/`ERROR`.
The wording remains meaningful in terminals that do not display color.

Returning an active Cartographer setup to stock PR Touch is shown as a planned
recovery workflow but is not enabled yet. The existing stock installer will not
attempt an unsafe partial conversion.

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

> [!NOTE]
> Some Cartographer V3 / Survey boards may fail during a normal USB/Katapult
> write until their bootloader and firmware have been restored. Put the probe
> into true DFU mode, run the bundled DFU recovery with **V3** selected, then
> unplug/replug the probe or power-cycle the printer. Rerun the normal flasher
> afterward to verify communication. Use STM32CubeProgrammer from another
> computer only if the bundled printer-side DFU recovery also fails.

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

Extras are installed individually from **Optional extras**.

| Extra | Purpose / requirement |
|---|---|
| [Cartographer offset setup](./installer/extras/cartographer-offset-setup/README.md) | Select Jamin, JimmyV, or custom probe offsets; requires Cartographer. |
| Cartographer plate workflow ([macros](./installer/extras/cartographer-macros/README.md), [automatic selection](./installer/extras/surface-selection-wrapper/README.md)) | Installs the predefined `CARTO_*` controls and slicer-driven plate selection together; requires Cartographer. |
| [Axis twist compensation](./features/axis_twist_compensation/README.md) | Optional compensation for Z drift across X. |
| [KAMP adaptive purge](./installer/extras/kamp-adaptive-purge/README.md) | Adds the adaptive purge feature. |
| [R3MEN bed profile](./features/r3men-bed/README.md) | Adds the R3MEN graphite-bed thermistor profile. |
| [Secure Auth](./features/secure-auth/README.md) ([key setup guide](./features/secure-auth/SETUP.md)) | Disables SSH password login only after a valid-looking public key is detected. Follow the setup guide and test the key in a second terminal first. |
| [PR Touch cleanup](./installer/extras/prtouch-cleanup/README.md) | Removes an orphan `[prtouch_v3]` `SAVE_CONFIG` header. |

## Updating

Use **6. Update installer** from the main menu, rerun either bootstrap command above, or run:

```sh
cd /mnt/UDISK/root/k2-improvements
git pull --ff-only
```

## Factory reset and cleanup

**Maintenance and recovery -> Factory reset and cleanup tools** provides a dry
run and a separately confirmed destructive reset. Review the dry run first.

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

This project was originally started by [Jamin Collins](https://github.com/jamincollins/k2-improvements). [Jacob10383](https://github.com/Jacob10383/k2-improvements) forked that foundation, expanded its features and installers, and continues to maintain and develop the project. Jacob had also planned a menu-driven installation path.

The working menu implementation in this fork is based substantially on [erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24). That fork provided the practical foundation and design reference for the guided menu system, which has since been reorganized and extended here with setup detection, resumable install paths, status reporting, recovery tools, and additional safety checks.

The Cartographer plate-profile macros and automatic slicer surface-selection workflow are also adapted from erondiel's work.

Original-project acknowledgements:

- [@Guilouz](https://github.com/Guilouz)
- [@stranula](https://github.com/stranula)
- [@juliosueiras](https://github.com/juliosueiras)
- [Moonraker](https://github.com/Arksine/moonraker)
- [Klipper](https://github.com/Klipper3d/klipper)
- [Fluidd](https://github.com/fluidd-core/fluidd)
- [Entware](https://github.com/Entware/Entware)
- [Cartographer 3D](https://github.com/Cartographer3D)

Donations to support Jacob's continued maintenance and development are available through [Jacob10383's Ko-fi](https://ko-fi.com/jacob10383).

## Disclaimer

Use this software at your own risk. The maintainers and contributors are not responsible for damage to the printer, probe, configuration, or other property.
