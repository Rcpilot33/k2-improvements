# Better Root

Moves the root user's home directory from the small system filesystem to
`/mnt/UDISK/root`.

This provides enough space for Klipper-related repositories and gives the K2
Plus a conventional layout containing paths such as:

```text
klipper
klippy-env
moonraker
moonraker-env
printer_data
```

## What to expect

The installer:

1. Copies missing root-home files to `/mnt/UDISK/root` and preserves existing files there.
2. Updates `/etc/passwd` with the new home directory.
3. Creates the required links to the printer software and configuration.
4. Keeps the SSH session open when run from bootstrap or the menu.

Reconnect to the printer after installation. Re-running the installer is safe
when Better Root is already active.
