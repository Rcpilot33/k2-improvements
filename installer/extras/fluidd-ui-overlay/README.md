# Fluidd settings capability check

The settings dialogs now live in the Rcpilot33/fluidd source and release ZIP.
This compatibility entry point checks k2-ui-overlay-support.txt (9 or newer).
It never installs an archive, swaps Fluidd files, or restarts nginx.

Bed Assist, Global Carto Scan/Touch, Global No-Carto, and Material Z-offset
editors continue to call this entry point before installing their backend.
Older Fluidd builds must be upgraded through the Fluidd core installer first.
The previous bundled v1.37.4 ZIP and source patch have been retired.
