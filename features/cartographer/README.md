# Cartographer

Cartographer replaces the K2 Plus stock contact probe with a fast scanning
probe. It supports dense, adaptive bed meshes without the long probing time of
a large stock-probe mesh.

## Benefits

- Faster bed scanning
- Denser mesh data
- Adaptive meshing around the current print
- Separate scan and touch models for supported plate workflows

## Important differences

The K2 Plus uses a userspace USB bridge for Cartographer communication. The
installation therefore includes the probe plugin, bridge service, Klipper
configuration, and K2-specific macros.

Installing Cartographer replaces the active stock `prtouch_v3` configuration.
Choose the correct physical mount preset and power-cycle the printer before
the first homing move after installation.

## Hardware

- [Cartographer V4 AIO Standard](https://cartographer3d.com/products/cartographer-v4-aio-standard), or
  Cartographer V3 USB hardware
- Two M2.6x20 mm screws
- Two M3x5x4 heat-set inserts for the printed mount
- A compatible K2 Plus Cartographer mount

## Install and calibrate

Use **Install or change setup -> Install Cartographer setup** from the menu.
After installation:

1. Select the mount and offset profile that matches the installed hardware.
2. Power-cycle the printer before homing.
3. Follow the [Cartographer setup guide](./SETUP.md).
4. Flash probe firmware only if needed; firmware flashing is a separate menu
   action.

For automatic per-surface model selection, install the **Cartographer plate
workflow** from Extras and follow its
[selector/action guide](../../installer/extras/cartographer-macros/README.md).
