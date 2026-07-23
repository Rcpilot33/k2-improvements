# Secure Auth

Disables SSH password authentication so the K2 Plus accepts public-key login
only.

The installer refuses to make changes unless
`/etc/dropbear/authorized_keys` contains a valid-looking public key. Before
installing:

1. Follow the [key setup guide](./SETUP.md).
2. Confirm key login works in a second terminal.
3. Keep the current SSH session open until the test succeeds.

Incorrect key setup can lock you out of SSH access.
