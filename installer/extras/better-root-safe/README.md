# Better Root Safe Installer

Provides the Better Root behavior required by the guided installation paths
without interrupting an automated install.

## Differences from the original installer

- Does not create a symlink over an existing real directory.
- Leaves Moonraker paths for the Moonraker installer to configure.
- Does not terminate Dropbear or kill the active SSH connection.
- Exits cleanly when `/mnt/UDISK/root` is already the configured home.

## What it changes

1. Moves the existing `/root` content to `/mnt/UDISK/root`.
2. Updates the root home entry in `/etc/passwd`.
3. Creates safe links for Klipper, its environment, and `printer_data`.
4. Warns and skips any destination that contains a real directory.

The Moonraker installation path later creates and manages its own Moonraker
directories and services.

This safe variant is used by both guided setup paths. The original Better Root
installer remains available for compatibility with Jacob's entry points.
