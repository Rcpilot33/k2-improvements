# Fluidd

Installs the K2-compatible Fluidd build used by this project. It replaces the
older factory web interface, enables the K2 camera integration, registers
Fluidd with Moonraker's update manager, and restarts the web services.

Updated Moonraker must be installed first. Fluidd must provide native settings API 1, legacy overlay marker
8 with Unix line endings, and device-cards API 1. Older releases are rejected before replacing any UI.

Bed Assist, Global Carto Scan/Touch, Global No-Carto and Material Z-offset dialogs
now ship in the Fluidd source and release ZIP. The former overlay installer only
checks capabilities. Its old ZIP, source patch and bundle builder are retired.

The core installer also installs the managed `k2_device` Moonraker component and
adds `[include k2_device.conf]`. It connects only to `ws://127.0.0.1:9999` on the
printer. Fluidd uses Moonraker's authenticated WebSocket for status and commands;
no browser-side native port, cross-origin permission, or external daemon is needed.
The one managed component file is excluded locally from Moonraker's Git status,
so normal Moonraker source checks and updates remain usable. K2-improvements owns
bridge updates; Fluidd releases own the cards and settings dialogs.

Existing printers receive migration `fluidd-consolidated-device-cards-v3` through
the installer updater. It installs the combined Fluidd release if needed, updates
the bridge, and participates in the updater's Moonraker restart. Later UI-only
updates continue through Fluidd's existing Moonraker web updater.

## Update Fluidd from the installer

Select **6. Update installer /
apply updates -> 2. Review pending update actions -> Fluidd settings dialogs and
K2 device cards**. The normal maintenance/reinstall entry also uses the same
Fluidd core installer. No manual ZIP transfer is required.

The installer downloads the latest stable `fluidd.zip` from `Rcpilot33/fluidd`. Capability validation
runs before replacing any UI. A printer already on the compatible stable UI
keeps that UI while the installer adds or refreshes the bridge.

Migration `fluidd-stable-consolidated-release-v9` also covers printers that
completed the earlier test migrations. It restores the normal Fluidd web updater,
so future stable ZIP releases appear in Fluidd's software-update list.

Migration `fluidd-stable-build-verification-v10` also checks release metadata so
printers that completed v9 while still running a test UI receive the stable
release. Compatible stable installations keep their UI. Apply-all updates run
Fluidd after Moonraker and before the macros and Z-offset settings installers.

### Optional local ZIP installation

If you already have a compatible Fluidd ZIP, transfer it to the printer and
run the following command from this repository while the printer is idle.

```sh
sh features/fluidd/install.sh --archive /absolute/path/fluidd.zip --nocam
```

This installs the bridge, backs up the previous UI once as
`~/fluidd.before-k2-cards`, activates the validated build and restarts nginx and
Moonraker. A factory UI stored directly in `/usr/share/fluidd` is retained as
`/usr/share/fluidd.before-k2-cards`. Refresh the browser afterward. The normal
Fluidd web updater remains enabled for stable releases.

Verify each fan against the touchscreen, CFS colors/materials and external spool,
slot removal/reconnection, Feed/Retract while idle, and disabled controls while
printing, paused or disconnected. Native commands report **sent**, not completed.
Hardware movement and firmware-specific acceptance still require printer testing.
The initial card displays slots and auto-refill state; filament-profile editing,
RFID rereads and changing auto-refill are outside this first version.

For rollback, stop nginx, move the test UI aside, restore the saved UI directory
to its original path, and start nginx again. Remove only `[include k2_device.conf]`
from `moonraker.conf` and restart Moonraker to disable the bridge. Keep the saved
UI until printer testing is complete.

The installer updater can repair Fluidd's Moonraker update source without
replacing the installed UI. Its one-time cache reset briefly starts Moonraker
without the Fluidd updater, restoring the updater configuration before a second
restart. This clears remote release and download data left from a previous
repository. Verify the displayed release comes from `Rcpilot33/fluidd` before
using Moonraker's Fluidd Update button.
