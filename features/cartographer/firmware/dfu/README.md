# Cartographer offline DFU recovery

This recovery path is only for a Cartographer that cannot be updated through
the normal USB/Katapult `flash.py` path.

It supports Cartographer V3 and V4 over USB. The user must select the hardware
manually because both versions appear as `0483:df11` in true STM32 DFU mode.

The four bundled combined images contain Katapult plus the exact tested
Cartographer application firmware offered by `../flash.py`:

- V3 5.1.0 Full
- V3 5.1.0 K1/Lite
- V4 6.0.0 Full
- V4 6.0.0 Lite

Each image is checksum-verified before writing. Recovery writes at
`0x08000000`; never use these combined images with Katapult.

```sh
sh /mnt/UDISK/root/k2-improvements/features/cartographer/firmware/dfu/recover.sh
```

The recovery writer is based on MicroPython/OpenMV's MIT-licensed `pydfu.py`.
It reuses the PyUSB package already bundled with `flash.py` and the K2's system
`/usr/lib/libusb-1.0.so.0`, so no additional executable or internet connection
is required.
