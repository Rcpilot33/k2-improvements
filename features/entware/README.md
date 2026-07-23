# Entware

Installs the Entware package manager and the command-line tools required by
the K2 Plus improvements installers.

The installer places Entware under `/mnt/UDISK/opt`, links it to `/opt`, and
installs packages including Git, curl, jq, unzip, secure wget, and SFTP support.

## Important

- An internet connection is required.
- A repair installation replaces the existing `/opt` and `/mnt/UDISK/opt`
  directories.
- Normal users should install Entware through bootstrap. Use the individual
  component installer only to repair a failed or incomplete setup.
