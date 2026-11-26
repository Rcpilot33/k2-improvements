# K2 Improvements — K2 Plus and K2 Pro Menu Installer

> [!TIP]
> **Community and video guides**
>
> - 💬 [Join the official Rcpilot33 K2 Improvements Discord](https://discord.gg/696Updwwbn)
> - ▶️ [Watch Rcpilot33 K2 Improvements on YouTube](https://www.youtube.com/@Rcpilot33)

> [!IMPORTANT]
> **K2 Improvements supports the Creality K2 Plus (F008) and K2 Pro (F012).**
> Both models can use the stock PR Touch probe or Cartographer.

This fork is built on the primary technical work maintained by
[Jacob10383/k2-improvements](https://github.com/Jacob10383/k2-improvements).
It adds a guided, status-aware installer and documented installation,
calibration, and maintenance workflows for both printers.

## Start here

| What do you want to do? | Guide |
|---|---|
| Install K2 Improvements | [Prepare the printer](./INSTALL.md#before-installation), then [run the installer for your model](./INSTALL.md#bootstrap) |
| Set up for a first print | [Stock PR Touch](./INSTALL.md#stock-pr-touch-first-print-preparation) or [Cartographer setup and calibration](./features/cartographer/SETUP.md) |
| Configure OrcaSlicer or Creality Print | [Machine start, filament changes, and Fluidd layer reporting](./installer/extras/kamp-adaptive-purge/slicer-templates/README.md) |
| Add a feature | [Optional features and their guides](#optional-features) |
| Update an existing printer | [Update the installer](./INSTALL.md#updating) or [back up and restore settings around a firmware OTA](./INSTALL.md#recover-after-a-firmware-ota) |
| Troubleshoot a print or installation | [FAQ and troubleshooting](./FAQ.md) |

## Important warnings

> [!WARNING]
> These scripts modify the printer's rooted operating system, Klipper,
> Moonraker, Fluidd, firmware-facing services, and printer configuration. Use
> them entirely at your own risk and back up anything you want to preserve.
> The maintainers and contributors accept no responsibility or liability for
> printer or probe damage, data loss, failed prints, personal injury, fire, or
> any other loss resulting from installation or use.

> [!CAUTION]
> Do not use Klipper's host-only `RESTART` command or
> `/etc/init.d/klipper restart` by itself before homing. Configuration-only
> changes and protected `SAVE_CONFIG` use `FIRMWARE_RESTART`. Installers that
> replace loaded Klippy Python modules use a guarded host restart followed by
> firmware-reset recovery and the K2 initialization wait. If a protected
> sequence reports an error, power-cycle before running `G28`.

These improvements are not compatible with Creality Print's **Print
Calibration** option or Creality's automatic print-calibration workflow.
Leave that option disabled when sending a print, then use the provided manual
calibration, bed-mesh, and tuning workflows after installation. Enabling it can
insert a separate Creality-controlled bed-stabilization delay before
`START_PRINT`; see the [FAQ](./FAQ.md#can-i-still-use-the-automatic-calibration-features).

## Validated firmware

| Printer | Firmware compatibility |
|---|---|
| K2 Plus (F008) | Expected to work from `1.1.3.13` through `1.1.8.0` based on tests across multiple releases. For a new installation, choose `1.1.5.2` or later within that range for Creality's firmware fixes. |
| K2 Pro (F012) | `1.1.8.3` with stock PR Touch or Cartographer. Cartographer also completed a print on `1.1.5.5` after firmware recovery. |

Use the firmware image for your printer model. Both models have a release numbered `1.1.5.5`.

## Quick start

### Recommended clean starting point

For the most predictable installation, start with freshly installed firmware
or a factory-reset stock printer. Back up the printer configuration, custom
macros, saved meshes, calibration data, and anything else you want to keep
before resetting it.

Creality's standard factory reset can be requested from an existing root SSH
session with this command:

```sh
echo "all" | /usr/bin/nc -U /var/run/wipe.sock
```

> [!WARNING]
> This command is destructive. It removes the printer configuration and other
> user data. The SSH session is expected to disconnect while the printer
> resets. Afterward, repeat the printer's on-screen setup, reconnect it to the
> network, and enable root access again.

The standard reset may leave files from an existing K2 Improvements or other
third-party installation under `/mnt/UDISK`. For a previously modified
printer, follow the [factory-reset preparation and improved cleanup
instructions](./INSTALL.md#recommended-clean-starting-point) instead.

After installing the firmware or completing the reset:

1. Complete the printer's normal on-screen setup and factory calibrations.
2. Enable root access under **Settings → General → Root Account Information**.
3. Record the root password and printer IP address.
4. Connect over SSH as `root` on port `22` and make sure no print is active.

On either printer, run this command over SSH to install from `main`.

```sh
python3 -c 'import urllib.request; urllib.request.urlretrieve("https://raw.githubusercontent.com/Rcpilot33/k2-improvements/main/bootstrap.sh", "/tmp/bootstrap.sh")' && sh /tmp/bootstrap.sh --menu
```

Enter `y` when bootstrap offers to open the installer menu.

Bootstrap prepares the required command-line tools, persistent root
environment, and repository checkout. The menu then performs the printer setup
path or optional feature you select.

The same documented bootstrap command is also the installer recovery path. It
first attempts a normal fast-forward update. If the checkout has diverged or is
too old to update normally, bootstrap clones and verifies the selected branch
before replacing the checkout. It saves the previous checkout, including local
edits and any existing Git history, in
`/mnt/UDISK/root/.k2-improvements/bootstrap-recovery/previous-checkout/`.

For factory-reset preparation, Cartographer hardware and firmware steps,
unattended bootstrap, recovery procedures, and detailed menu behavior, read
the [complete installation guide](./INSTALL.md).

## Choose your path in the menu

| Goal | Menu path |
|---|---|
| Keep stock PR Touch | **Install or change setup → Stock probe** |
| Install Cartographer directly | **Install or change setup → Cartographer setup** |
| Add Cartographer later | **Install or change setup → Convert stock setup to Cartographer** |
| Add one optional feature | **Optional extras** |
| Repair one core component | **Maintenance and recovery → Core component installer** |
| Update installed components after an installer update | **Update installer → Update and review required actions** |
| Apply changed configuration or macros | **Maintenance and recovery → Apply macro or printer-setting updates** |
| Apply already-installed Klippy feature code | **Maintenance and recovery → Apply Klipper feature-code updates** |

The menu detects installed components, skips completed work, and reports what
was installed, skipped, or failed. The stock-probe installer will stop if it
detects Cartographer; it does not automatically convert a Cartographer printer
back to stock PR Touch.

Installer updates are tracked separately from installed printer components.
After pulling newer installer files, the menu recommends only migrations that
apply to features detected on that printer. Successful repairs are recorded so
the same migration is not repeatedly offered. A factory reset clears this
update-tracker state.

## Before the first print

### Stock PR Touch

Create and save a `default` bed mesh using the same `[bed_mesh] probe_count`
that will be active while printing. Recreate it whenever `probe_count` changes.
Saved `5,5` and `19,19` meshes are not interchangeable.

On the K2 Plus, run `G28`, `Z_TILT_ADJUST`, `G28 Z`,
`BED_MESH_CALIBRATE PROFILE=default`, and `SAVE_CONFIG` in that order, then
wait for the protected restart to finish before moving the printer.

For the single-Z K2 Pro, use the stock-probe Pro sequence in the
[bed-mesh guide](./features/macros/bed_mesh/README.md).

### Cartographer

Confirm that the selected mount profile matches the physical mount and required
spacers. The Jamin profile is printer-tested. The JimmyV legacy and final
profiles are **untested** and use JimmyV's published offsets. Final profiles
are provided for mounts without and with the 3DO nozzle camera. Custom offsets
are supported.

The Cartographer installer changes the untouched stock `19,19` probe count to
`50,50` and sets bed-mesh speed to `150` in `custom/overrides.cfg`. Full
firmware can use speed `200`; existing customized values are preserved during
updates.

Complete Scan and Touch calibration, then tune final print Z from an actual
first layer. Touch calibration selects the detection threshold and speed; its
saved `z_offset` is only the starting point for print tuning.

See the [Cartographer setup and calibration guide](./features/cartographer/SETUP.md).

## Optional features

Most extras are installed from **Optional extras**. Cartographer mount offsets
are under **Cartographer tools**, and PR Touch `SAVE_CONFIG` cleanup is under
**Maintenance and recovery**.

Choose **Optional extras -> Install multiple optional extras** to enter several
option numbers separated by spaces. Review the ordered selection, then answer
any feature settings questions. Existing selections are reinstalled/refreshed.
The batch runs while the printer is idle and defers activation until one final
protected Klippy code reload and firmware restart. It stops on an installer
failure, still attempts the final restart for changes already made, and reports
the incomplete batch. A failed restart leaves update verification pending;
power-cycle before homing if the restart reports an error.

Secure Auth, hardware conversion, legacy Axis Twist removal, and calibration
remain separate actions. Only select the R3MEN thermistor profile if that
replacement hardware is fitted. Run any required calibration after activation.

| Extra | Documentation |
|---|---|
| Cartographer mount offsets | [Offset setup](./installer/extras/cartographer-offset-setup/README.md) |
| Cartographer plate profiles and slicer selection | [Macro controls](./installer/extras/cartographer-macros/README.md) · [Automatic selection](./installer/extras/surface-selection-wrapper/README.md) |
| Global Carto Touch Z Offsets | [Live offset editor](./installer/extras/global-touch-offsets/README.md) |
| Material Z Offsets | [Material offset editor](./installer/extras/material-z-offsets/README.md) |
| KAMP adaptive purge | [KAMP guide and slicer templates](./installer/extras/kamp-adaptive-purge/README.md) |
| Remove legacy Axis Twist (manual, existing installs only) | [Optional stock-probe restoration](./installer/extras/axis-twist-removal/README.md); never included in Apply all updates |
| Plate-aware saved meshes | [Stock PR Touch plate-and-temperature mesh profiles](./installer/extras/plate-aware-mesh/README.md) |
| R3MEN bed thermistor profile | [R3MEN guide](./features/r3men-bed/README.md) |
| Stock nozzle camera stream | [Factory nozzle-camera guide](./installer/extras/nozzle-camera/README.md) |
| Secure Auth | [Overview](./features/secure-auth/README.md) · [Key setup](./features/secure-auth/SETUP.md) |
| PR Touch `SAVE_CONFIG` cleanup | [Cleanup guide](./installer/extras/prtouch-cleanup/README.md) |

## Documentation

- [Step-by-step K2 Plus installation, calibration, and troubleshooting videos](https://www.youtube.com/@Rcpilot33)
- [Complete installation, update, and recovery guide](./INSTALL.md)
- [Cartographer setup and calibration](./features/cartographer/SETUP.md)
- [Cartographer firmware and DFU recovery](./features/cartographer/firmware/README.md)
- [Slicer `START_PRINT` setup](./features/macros/start_print/README.md)
- [FAQ and troubleshooting](./FAQ.md)
- [Bed measurement and shimming](./bed_leveling)

## Project lineage and credits

- [Jamin Collins (`jamincollins`)](https://github.com/jamincollins/k2-improvements)
  created the original K2 Improvements project and deserves original-author
  and first-project credit.
- [Jacob10383](https://github.com/Jacob10383/k2-improvements) substantially
  expanded Jamin's foundation. This fork continues to depend on components
  developed in Jacob's related repositories. Major technical credit belongs to
  Jacob and his contributors.
- The menu structure and guided workflow were influenced substantially by
  [erondiel's `v1.1.24` fork](https://github.com/erondiel/k2-improvements/tree/v1.1.24).
  The plate-profile macros and automatic slicer surface-selection workflow are
  also adapted from erondiel's work.

Additional acknowledgements:

- [@Guilouz](https://github.com/Guilouz)
- [@stranula](https://github.com/stranula)
- [@juliosueiras](https://github.com/juliosueiras)
- [Moonraker](https://github.com/Arksine/moonraker)
- [Klipper](https://github.com/Klipper3d/klipper)
- [Fluidd](https://github.com/fluidd-core/fluidd)
- [Entware](https://github.com/Entware/Entware)
- [Cartographer 3D](https://github.com/Cartographer3D)

## License

The installer is licensed under the [GNU General Public License v3.0](./LICENSE).
Third-party components retain their own license terms.

## Disclaimer

This software is provided without warranty. Installation and use are entirely
at the user's risk. The maintainers and contributors are not responsible or
liable for printer or probe damage, configuration or data loss, failed prints,
personal injury, fire, or any other direct or indirect loss.
