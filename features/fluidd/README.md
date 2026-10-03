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
