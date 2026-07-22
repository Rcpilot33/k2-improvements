# Secure Auth

## Why?

The Creality K2 has a well known username and password for remote SSH access.

Provided there is a [key configured for ssh authentication](./SETUP.md), this disables all password ssh authentication.

The installer refuses to make any changes unless
`/etc/dropbear/authorized_keys` contains a valid-looking SSH public-key entry.
Before installing, verify that the key works from a second terminal and keep
the current SSH session open until that test succeeds.
