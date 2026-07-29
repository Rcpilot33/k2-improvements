# Complete Installation and Recovery Guide

This guide contains the detailed installation, update, maintenance, and
recovery information for the K2 Plus Improvements menu installer. For the
project overview and shortest supported path, begin with the
[main README](./README.md).

## Safety and compatibility

> [!WARNING]
> These scripts modify the printer's rooted operating system, Klipper,
> Moonraker, Fluidd, firmware-facing services, and printer configuration. Use
> them entirely at your own risk and back up anything you want to preserve.
> The maintainers and contributors accept no responsibility or liability for
> printer or probe damage, data loss, failed prints, personal injury, fire, or
> any other loss resulting from installation or use.

> [!CAUTION]
> After an installer, `SAVE_CONFIG`, or `FIRMWARE_RESTART` restarts Klipper,
> fully reboot or power-cycle the printer **before running `G28`**. A known K2
> Plus motor-state issue can otherwise cause homing in the wrong direction.

The modifications are not compatible with Creality's automatic calibration
workflow. Complete the factory setup before installing, then use the provided
manual calibration, bed-mesh, and tuning workflows.

Validated Creality firmware versions are `1.1.3.13`, `1.1.5.2`, and `1.1.5.5`.
See [VALIDATION.md](./VALIDATION.md) for the complete test matrix.

## Before installation

### Complete the stock setup

On a fresh or reset printer:

1. Complete the full on-screen Creality setup.
2. Run its factory calibrations, including cutter calibration and input shaping.
3. Restore the network connection.
4. Enable root access under **Settings → General → Root Account Information**.
5. Record the root password and printer IP address.
6. Connect over SSH as `root` on port `22`.
7. Make sure no print is active.

[MobaXterm](https://mobaxterm.mobatek.net/) is a convenient Windows SSH client
and includes a graphical SFTP browser.

### Back up the printer

Back up the printer configuration, custom macros, saved meshes, calibration
data, and any other files you want to keep. A factory reset and some recovery
operations are destructive.

### Optional stock factory reset

Creality's standard reset can be triggered over SSH:

```sh
echo "all" | /usr/bin/nc -U /var/run/wipe.sock
```

> [!WARNING]
> This command is destructive. Do not run it until the required files are
> backed up. After the reset, complete the stock on-screen setup before
> installing these modifications.

The standard `wipe.sock` reset does not reliably remove every leftover
top-level directory under `/mnt/UDISK`. When replacing or recovering an
existing K2 Improvements or other third-party installation, use the menu's
**Maintenance and recovery → Factory reset and cleanup tools** instead. Its
`factory-reset-improved` workflow removes the leftover UDISK directories
identified by its dry run and then invokes the standard `wipe.sock` reset.

## Bootstrap

Bootstrap installs Entware when needed, configures the larger persistent root
home, and clones or updates this branch at:

```text
/mnt/UDISK/root/k2-improvements
```

### Bootstrap and open the menu

Copy this entire command into the printer's SSH session:

```sh
python3 -c 'import urllib.request; urllib.request.urlretrieve("https://raw.githubusercontent.com/Rcpilot33/k2-1155-Jacob-Fork/k2-1155-compat/bootstrap.sh", "/tmp/bootstrap.sh")' && sh /tmp/bootstrap.sh localhost --menu
```

The `--menu` path asks whether to open the installer after bootstrap. Enter
`y` to continue. A blank answer, `n`, or input failure finishes bootstrap
without opening the menu.

### Bootstrap without the menu prompt

Use this form to install or update only the bootstrap and repository:

```sh
python3 -c 'import urllib.request; urllib.request.urlretrieve("https://raw.githubusercontent.com/Rcpilot33/k2-1155-Jacob-Fork/k2-1155-compat/bootstrap.sh", "/tmp/bootstrap.sh")' && sh /tmp/bootstrap.sh localhost --no-menu
```

The default when no menu flag is supplied is also `--no-menu`.

On the first run, `better-root` may intentionally close the SSH connection.
Reconnect and open the menu with:

```sh
sh /mnt/UDISK/root/k2-improvements/menu.sh
```

If an HTTPS download reports that a certificate is not yet valid, verify the
printer's date, time, and timezone. Correct them from the printer screen or
synchronize the clock before retrying bootstrap.

## Prepare Cartographer hardware

Skip this section when keeping stock PR Touch.

Complete the stock Creality setup first. Then:

1. Power off the printer.
2. Install the correct Cartographer mount and any required spacers.
3. Install the wiring and USB connection.
4. Confirm whether the probe is Cartographer V3 or V4.
5. Power on, run bootstrap, and open the installer.
6. Review **Cartographer tools → Firmware flash** before installing the
   Cartographer software path.

Use only the bundled firmware matching the connected hardware. Selecting the
wrong mount profile, omitting required spacers, or flashing firmware for the
wrong hardware can produce incorrect probe positioning or leave the probe
unavailable.

## Choose the setup path

| Goal | Menu path | Behavior |
|---|---|---|
| Keep stock PR Touch | **Install or change setup → Stock probe** | Installs the supported core stack without Cartographer. |
| Install Cartographer | **Install or change setup → Cartographer setup** | Installs Cartographer and offers the required mount-offset picker. |
| Convert an installed stock setup | **Install or change setup → Convert stock setup to Cartographer** | Retains and skips compatible components already installed by the stock path. |
| Install an optional feature | **Optional extras** | Shows its current state and runs only that installer. |
| Repair a core component | **Maintenance and recovery → Core component installer** | Opens the advanced individual-component menu. |

The guided installers run dependencies in order. Before each step, the menu
checks the installed state and skips completed components. The final summary
reports installed, skipped, and failed steps.

The stock installer does not remove an existing Cartographer installation or
convert a Cartographer printer back to stock PR Touch. It stops when
Cartographer is detected.

## Main menu reference

| Item | Purpose |
|---:|---|
| 1 | Show installation, firmware, Cartographer, component, and extras status. |
| 2 | Install, repair, or change the printer setup path. |
| 3 | Open Cartographer firmware, recovery, mount-offset, and calibration tools. |
| 4 | Install optional hardware, print-workflow, and security extras. |
| 5 | Open component repair, PR Touch cleanup, and factory-reset tools. |
| 6 | Update the installer with a fast-forward-only pull and reload the menu. |
| 0 | Exit. |

States are displayed as words so they remain meaningful without terminal
color:

- Green: `INSTALLED` or `COMPLETE`
- Gray: `NOT INSTALLED` or `AVAILABLE`
- Yellow: `REQUIRES ...`, `INCOMPLETE`, or `RECOVERY`
- Red: `DESTRUCTIVE` or `ERROR`

Returning an active Cartographer setup to stock PR Touch is a planned recovery
workflow and is not currently enabled.

## Installed core components

The Cartographer path adds Cartographer and its cleanup step. The stock path
omits those components.

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
| [Macros](./features/macros/README.md) | Installs `START_PRINT`, `M191`, bed-mesh, and overrides support. |

Optional quality-of-life and hardware-specific features are deliberately
excluded from the guided core installation paths.

## Stock PR Touch first-print preparation

Before the first print, create and save a bed mesh named `default` using the
same `[bed_mesh] probe_count` that will be active during printing. The stock
temperature-specific mesh workflow expects a compatible saved default mesh.

If `probe_count` changes, recreate and save `default` before printing. A `5,5`
default and a `19,19` configuration cannot be mixed, nor can a `19,19` default
be reused after changing the active configuration to `5,5`.

See the [bed-mesh guide](./features/macros/bed_mesh/README.md).

## Cartographer firmware and recovery

Firmware flashing is a separate explicit action because it requires the probe
to be connected and may require physical access.

### Normal USB/Katapult flashing

The normal flasher:

- Detects the connected V3 or V4 hardware
- Enters Katapult automatically when possible
- Offers only bundled, tested firmware
- Writes and verifies the selected image

| Hardware | Full recommendation | Lite fallback |
|---|---|---|
| Cartographer V3 / STM32F042 | `5.1.0` | `K1 5.1.0` |
| Cartographer V4 / STM32G431 | `6.0.0` | `V4 6.0.0 Lite` |

Full is recommended for the K2 Plus. Lite is a conservative fallback for
timing problems.

### Bundled STM32 DFU recovery

Use DFU only when normal USB/Katapult flashing cannot communicate with the
probe. V3 and V4 both appear as `0483:df11` in true STM32 DFU mode, so the
recovery menu requires manual hardware selection.

DFU recovery:

- Requires physically placing the probe into DFU mode using its pads
- Requires confirming V3 or V4 before writing
- Uses checksum-verified combined images bundled in the repository
- Writes Katapult and Cartographer firmware at `0x08000000`
- Does not require internet access during recovery

Selecting the wrong image requires reflashing the correct one. Some V3/Survey
boards may need bundled DFU recovery before a normal USB/Katapult write will
work. After DFU recovery, unplug/replug the probe or power-cycle the printer,
then rerun the normal flasher to verify communication.

Use STM32CubeProgrammer from another computer only if printer-side recovery
also fails. Read the complete
[Cartographer firmware guide](./features/cartographer/firmware/README.md).

## Cartographer mount offsets and calibration

The installer offers a mount picker after the automated Cartographer steps:

- **Jamin:** tested on printer hardware
- **JimmyV:** untested; uses JimmyV's documented mount offsets
- **Custom:** uses offsets entered by the user

Managed values are written to `overrides.cfg`, where they take precedence
without deleting inherited `cartographer.cfg` values. The tool retains only
the two newest `overrides.cfg.before-cartographer-offset-*` backups.

After a complete power cycle, follow the
[Cartographer setup and calibration guide](./features/cartographer/SETUP.md).
The mount, offsets, and calibration model must match the physical installation
and build surface.

## Optional extras

Install extras individually from **Optional extras**:

| Extra | Purpose |
|---|---|
| [Cartographer offset setup](./installer/extras/cartographer-offset-setup/README.md) | Select Jamin, JimmyV, or custom offsets; requires Cartographer. |
| Cartographer plate workflow ([macros](./installer/extras/cartographer-macros/README.md), [automatic selection](./installer/extras/surface-selection-wrapper/README.md)) | Installs selector/action controls and slicer-driven surface selection; requires Cartographer. |
| [Axis twist compensation](./features/axis_twist_compensation/README.md) | Compensates optional Z drift across X. |
| [KAMP adaptive purge](./installer/extras/kamp-adaptive-purge/README.md) | Installs the patched adaptive purge workflow and slicer templates. |
| [R3MEN bed profile](./features/r3men-bed/README.md) | Adds the R3MEN graphite-bed thermistor profile. |
| [Secure Auth](./features/secure-auth/README.md) | Disables SSH password login only after detecting a valid-looking public key. |
| [PR Touch cleanup](./installer/extras/prtouch-cleanup/README.md) | Removes an orphan `[prtouch_v3]` `SAVE_CONFIG` header. |

Follow the [Secure Auth key guide](./features/secure-auth/SETUP.md) and test the
key in a second terminal before disabling password login.

## Updating

Use **6. Update installer**, rerun either bootstrap command, or run:

```sh
cd /mnt/UDISK/root/k2-improvements
git pull --ff-only
```

The update is intentionally fast-forward-only. If local modifications make the
branch diverge or would be overwritten, the pull stops instead of silently
discarding them. Inspect `git status --short` and `git diff` before deciding
whether to preserve or restore those local files.

Feature installers can create backup files beside managed configuration files.
These backups are not intended to remain inside the Git repository. The
current surface-selection installer stores its backups outside the repository
so they do not block later updates.

## Factory reset and cleanup

**Maintenance and recovery → Factory reset and cleanup tools** offers a dry
run and two separately confirmed destructive reset paths:

1. **Improved cleanup + Creality factory reset** preserves
   `/mnt/UDISK/root` and `/mnt/UDISK/bin`, removes most other top-level UDISK
   directories—including `/mnt/UDISK/printer_data`—and then sends `all` to
   Creality's `wipe.sock`. Review the dry run first.
2. **Creality factory reset only** sends `wipe.sock all` without pre-deleting
   UDISK directories. Third-party files that Creality does not remove may
   remain afterward.

Both paths are destructive. Configuration, custom macros, saved meshes, logs,
and backups may be removed. On success, `wipe.sock` normally returns `ok` and
the printer reset terminates the SSH session. A remaining menu session with a
large failure banner means the reset did not complete.

### Firmware reinstall does not always restore a clean state

Reinstalling or changing Creality firmware may leave persistent configuration
or modified files under `/mnt/UDISK`. If the printer still enters the same
Klipper error state after a firmware reinstall, inspect
`/mnt/UDISK/printer_data/logs/klippy.log` rather than assuming the firmware
image itself is defective.

The generic touchscreen code `XS3002` does not identify the root cause. One
confirmed post-update failure paired stock `prtouch_v3_wrapper.py` with an
incompatible `bed_mesh.py` interface. Before that update, an attempted improved
menu reset had failed while removing a live directory and stopped before
reaching `wipe.sock all`. The newer firmware was therefore installed without a
completed factory wipe. Running the plain `wipe.sock all` command afterward
restored a matched stock environment.

This sequence does not prove that a correctly completed wipe followed by a
cross-version update produces the same failure. A successful menu reset reaches
`Begin factory reset...`, receives `ok`, and terminates the SSH connection as
the printer resets. Do not copy an arbitrary upstream Klipper module onto the
printer because Creality's K2 Plus build contains vendor-specific interfaces.

See the [XS3002 recovery entry in the FAQ](./FAQ.md) for log commands and the
validated recovery sequence.

## Legacy entry points

Inherited entry points remain available:

```sh
sh /mnt/UDISK/root/k2-improvements/gimme-the-jamin.sh
sh /mnt/UDISK/root/k2-improvements/no-carto.sh
```

The menu paths are recommended because they report status, skip completed
work, enforce prerequisites, and provide clearer recovery instructions.

## Additional help

- [FAQ and troubleshooting](./FAQ.md)
- [Validation report](./VALIDATION.md)
- [Bed measurement and aluminium-tape shimming](./bed_leveling)
- [Cartographer setup and calibration](./features/cartographer/SETUP.md)
- [Slicer `START_PRINT` setup](./features/macros/start_print/README.md)
