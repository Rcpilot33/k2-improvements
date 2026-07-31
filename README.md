# K2 Plus Improvements — Menu Installer

This fork is built on the primary technical work maintained by
[Jacob10383/k2-improvements](https://github.com/Jacob10383/k2-improvements).
It adds a guided, status-aware installer and firmware-aware workflows for the
Creality K2 Plus.

The menu provides separate, resumable paths for:

- Keeping the stock PR Touch probe
- Installing Cartographer V3 or V4
- Converting an existing no-Cartographer setup to Cartographer
- Installing optional features individually
- Diagnosing, flashing, recovering, and maintaining the installation

## Important warnings

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

These improvements are not compatible with Creality's automatic calibration
workflow. Use the provided manual calibration, bed-mesh, and tuning workflows
after installation.

## Validated firmware

All three installation paths have completed real install-and-print validation:

| Creality firmware | Stock PR Touch | Straight Cartographer | Stock → Cartographer |
|---|:---:|:---:|:---:|
| `1.1.3.13` | PASS | PASS | PASS |
| `1.1.5.2` | PASS | PASS | PASS |
| `1.1.5.5` | PASS | PASS | PASS |

Testing covered material offsets, KAMP and standard purge profiles,
Cartographer default fallback and plate selection, and switching between PLA
and PETG. See the [complete validation report](./VALIDATION.md).

Cartographer V3 and V4 normal USB/Katapult flashing and bundled STM32 DFU
recovery have also been tested on printer hardware.

## Quick start

Before beginning:

1. Complete the printer's normal on-screen setup and factory calibrations.
2. Enable root access under **Settings → General → Root Account Information**.
3. Record the root password and printer IP address.
4. Connect over SSH as `root` on port `22` and make sure no print is active.
5. Back up the printer configuration and anything else you want to preserve.

Copy this entire command into the printer's SSH session:

```sh
python3 -c 'import urllib.request; urllib.request.urlretrieve("https://raw.githubusercontent.com/Rcpilot33/k2-improvements/main/bootstrap.sh", "/tmp/bootstrap.sh")' && sh /tmp/bootstrap.sh localhost --menu
```

Enter `y` when bootstrap offers to open the installer menu.

Bootstrap prepares the required command-line tools, persistent root
environment, and repository checkout. The menu then performs the printer setup
path or optional feature you select.

> [!NOTE]
> On the first run, `better-root` may intentionally close the SSH connection.
> Reconnect and run:
>
> ```sh
> sh /mnt/UDISK/root/k2-improvements/menu.sh
> ```

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

The menu detects installed components, skips completed work, and reports what
was installed, skipped, or failed. The stock-probe installer will stop if it
detects Cartographer; it does not automatically convert a Cartographer printer
back to stock PR Touch.

## Before the first print

### Stock PR Touch

Create and save a `default` bed mesh using the same `[bed_mesh] probe_count`
that will be active while printing. Recreate it whenever `probe_count` changes.
Saved `5,5` and `19,19` meshes are not interchangeable.

See the [bed-mesh guide](./features/macros/bed_mesh/README.md).

### Cartographer

Confirm that the selected mount profile matches the physical mount and required
spacers. The Jamin profile is printer-tested. The JimmyV profile is
**untested** and uses JimmyV's documented offsets. Custom offsets are supported.

Complete Scan and Touch calibration, then tune final print Z from an actual
first layer. Touch calibration selects the detection threshold and speed; its
saved `z_offset` is only the starting point for print tuning.

See the [Cartographer setup and calibration guide](./features/cartographer/SETUP.md).

## Optional features

Install extras individually from **Optional extras**:

| Extra | Documentation |
|---|---|
| Cartographer mount offsets | [Offset setup](./installer/extras/cartographer-offset-setup/README.md) |
| Cartographer plate profiles and slicer selection | [Macro controls](./installer/extras/cartographer-macros/README.md) · [Automatic selection](./installer/extras/surface-selection-wrapper/README.md) |
| KAMP adaptive purge | [KAMP guide and slicer templates](./installer/extras/kamp-adaptive-purge/README.md) |
| Axis twist compensation | [Axis twist guide](./features/axis_twist_compensation/README.md) |
| R3MEN bed thermistor profile | [R3MEN guide](./features/r3men-bed/README.md) |
| Secure Auth | [Overview](./features/secure-auth/README.md) · [Key setup](./features/secure-auth/SETUP.md) |
| PR Touch `SAVE_CONFIG` cleanup | [Cleanup guide](./installer/extras/prtouch-cleanup/README.md) |

## Documentation

- [Complete installation, update, and recovery guide](./INSTALL.md)
- [Firmware and feature validation report](./VALIDATION.md)
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
  expanded Jamin's foundation and continues to maintain the primary technical
  project on which this fork depends. Primary ongoing project credit belongs
  to Jacob and his contributors.
- The menu and firmware-aware workflow were influenced substantially by
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

Donations supporting Jacob's continued maintenance and development are
available through [Jacob10383's Ko-fi](https://ko-fi.com/jacob10383).

## Disclaimer

This software is provided without warranty. Installation and use are entirely
at the user's risk. The maintainers and contributors are not responsible or
liable for printer or probe damage, configuration or data loss, failed prints,
personal injury, fire, or any other direct or indirect loss.
