# Fluidd

Installs the K2-compatible Fluidd build used by this project. It replaces the
older factory web interface, enables the K2 camera integration, registers
Fluidd with Moonraker's update manager, and restarts the web services.

Updated Moonraker must be installed first.

The installer updater can repair Fluidd's Moonraker update source without
replacing the installed UI. Its one-time cache reset briefly starts Moonraker
without the Fluidd updater, restoring the updater configuration before a second
restart. This clears remote release and download data left from a previous
repository. Until `Rcpilot33/fluidd` publishes a release, Fluidd should show
no available update; do not use Moonraker's Update button while the old release
is still displayed.


## Fluidd-first compatibility test

On `fluidd-upgrade-compatibility-test`, the core installer downloads the exact
prerelease in `test-release.json` and verifies its SHA256 before activation.
The legacy settings installers are unchanged from `integration-testing`.
No device bridge is installed. The previous UI is backed up at
`~/fluidd.before-upgrade-compatibility`. Stable web updates are disabled for
this pinned test to prevent replacement by the stable ZIP.

Update the installer with main-menu option 6, then use Maintenance and recovery,
Core component installer, fluidd, accepting the reinstall prompt.
Verify existing Bed Assist and offset dialogs, then rerun their feature
installers and confirm that the Fluidd build remains intact.

Validation: the published ZIP was downloaded with the printer's checksum
helper. The unchanged legacy overlay installer accepted it and preserved every
UI asset, including with a simulated newer version v1.37.5.
Fluidd lint, type-check, production build, and all 341 unit tests passed.
Hardware compatibility on the freshly installed printer is still pending.

To repeat the archive check, set `FLUIDD_TEST_ARCHIVE` to the local ZIP and run
`python3 features/fluidd/test_upgrade_compatibility.py`.
