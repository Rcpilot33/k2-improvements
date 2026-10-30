# Moonraker

Replaces the limited factory Moonraker installation with the K2-compatible
build used by this project.

Benefits include:

- log rotation for manageable `klippy.log` and `moonraker.log` files;
- service control through Fluidd;
- Home Assistant compatibility; and
- support for integrations such as [SimplyPrint](https://simplyprint.io/).

The installer creates a dedicated virtual environment, updates the service
configuration, and preserves the K2-specific service integrations.

## Maintained K2 source

New installs use `https://github.com/Rcpilot33/moonraker.git`, branch `k2`.
Do not use upstream `master` on a K2: the K2 compatibility changes are retained
in the maintained fork. Jacob's contributions and upstream history remain intact.

Existing installations receive the **Moonraker maintained K2 fork** recommended
update. Apply only while idle. It checks for a recognized origin, clean `k2`
checkout, fast-forward ancestry, and matching fork updater metadata. Unknown,
modified, detached or diverged checkouts are left alone. Dependency/install-script
changes require a full installation instead of this source-only migration.

The migration backs up Git configuration and records old/new commits beneath
`~/.k2-improvements/repository-recovery/moonraker-source-*`. It preserves
`moonraker.conf`, includes, database, virtualenv and Klipper configuration. Only
Moonraker is restarted when this update is applied alone; no Klipper firmware
restart is requested. Never apply maintenance during a print.

The fork must first publish its matching `common.py` updater defaults: origin
`https://github.com/Rcpilot33/moonraker.git`, primary branch `k2`, channel `dev`.
The installer refuses migration if these are missing, so update/recovery cannot
silently point back to upstream master. `dev` follows this compatibility branch;
it does not select upstream's development branch. This change does not pull
future changes from Jacob automatically or replace any printer firmware.

Local checks: `python -m unittest discover -s features/moonraker -p 'test_*.py'`.
