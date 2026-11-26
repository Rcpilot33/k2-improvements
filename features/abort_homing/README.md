# Abort Homing

Adds the Klipper `force_stop_homing` endpoint. A compatible interface can use
it to interrupt an active homing move and then disable the motors.

**Installed** in the installer diagnostics refers to the Klipper patch. The
project's Fluidd v1.37.5 and v1.37.6 interfaces lack a **Force Stop Homing**
button.

## Install

Use **Maintenance and recovery -> Core component installer**, or run:

```sh
sh install.sh
```

The installer patches a loaded Klippy Python module, then performs the
protected Klippy host reload, firmware-reset recovery, and K2 motor
initialization wait before returning.
