# Cartographer Firmware

A flashing script is included for Cartographer V3 and V4 probes connected to
the K2 Plus by USB. With this repository installed, run:

```sh
python3 /mnt/UDISK/root/k2-improvements/features/cartographer/firmware/flash.py
```

The main installer menu also provides this under **Cartographer tools → Normal
USB/Katapult firmware flash**. Connect only the probe you intend to flash and
follow the prompts. The flasher detects V3 or V4 hardware and offers only the
matching bundled Full and Lite firmware.

## Bundled DFU recovery

Use DFU recovery only when normal USB/Katapult flashing cannot communicate with
or write to the probe. V3 and V4 both appear as `0483:df11` in true STM32 DFU
mode, so you must select the hardware version manually.

From the installer menu, choose **Cartographer tools → DFU recovery flash**.
The recovery path:

- Uses checksum-verified combined images bundled with this repository
- Does not download firmware while recovering the probe
- Writes both Katapult and Cartographer firmware at `0x08000000`
- Requires the physical DFU pads to put the probe into true DFU mode

Selecting the wrong hardware image requires reflashing the correct image.

> [!NOTE]
> Some Cartographer V3 / Survey boards may fail during a normal USB/Katapult
> write until their bootloader and firmware have been restored. Run the bundled
> V3 DFU recovery first, unplug/replug the probe or power-cycle the printer, and
> then rerun the normal flasher to verify communication. Use
> STM32CubeProgrammer from another computer only if bundled recovery also fails.

Without bootstrap, copy the complete `firmware` directory to the printer so
that the flasher, DFU writer, dependencies, and bundled images remain together.

For the upstream flashing guide, see the
[official Cartographer documentation](https://docs.cartographer3d.com/cartographer-probe/firmware/updating-firmware).
