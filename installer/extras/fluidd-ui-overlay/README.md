# Shared Fluidd settings controls

This internal installer carries one verified Jacob Fluidd `v1.37.4` overlay for
the core Bed Assist editor and the optional Global Carto Scan/Touch and Material
Z-offset editors. Keeping all three dialogs in one archive prevents one feature
from replacing another feature's UI.

The normal Fluidd core installer and update source are unchanged. The overlay
uses an atomic directory swap, retains the original pre-overlay backup, and
restarts only nginx after a successful validation.

For audit/reproduction, apply `fluidd-v1.37.4.patch` to Jacob's matching
Fluidd source tree with `git apply --unidiff-zero`, build it, preserve Jacob's
`v1.37.4` release metadata, then package the dist directory using
`build_bundle.py`.
