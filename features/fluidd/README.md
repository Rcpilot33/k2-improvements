# Fluidd

This test branch points Moonraker's Fluidd update manager at
`Jacob10383/fluidd`. On an idle printer already running Fluidd v1.37.4,
verify that the installed `~/printer_data/config/updates/fluidd.cfg` also
names that repository, then use only the **fluidd** Update button in Fluidd's
Software Updates page to evaluate Jacob's v1.37.6 UI. Switching the bootstrap
branch alone does not replace the installed update-manager configuration.

The bundled settings-controls overlay still requires v1.37.4, so its Bed
Assist, Global Touch Offset, and Material Z Offset dialogs will be unavailable
after the UI update until that overlay is ported. This UI-only test does not
require rerunning the complete setup or the macros installer.

The core Fluidd component installer remains unchanged from main: it installs
the K2-compatible release from `Rcpilot33/fluidd`, enables the K2 camera
integration, registers the branch's update-manager configuration, and restarts
the web services.

Updated Moonraker must be installed first.
