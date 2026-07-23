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
