# Abort Homing

Adds the backend support required by the custom Fluidd **Force Stop Homing**
button.

Use it to stop an incorrect homing move without issuing a full emergency stop.
This is especially useful if an axis begins moving in the wrong direction.

![Abort Homing button](image.png)

## Install

Use **Maintenance and recovery -> Core component installer**, or run:

```sh
sh install.sh
```

The installer patches Klipper and restarts the service. Power-cycle the printer
before the next `G28`.
