# Secure Auth key setup

Secure Auth disables SSH password login on the printer. Before installing it,
you must place an SSH public key on the printer and prove that the matching
private key can open a second SSH session.

> **Do not install Secure Auth until the key-only test in step 4 succeeds.**
> Keep your original SSH session connected while performing the test.

## What you need

- The printer's IP address, such as `192.168.1.239`
- The printer's current root password
- [Git for Windows](https://git-scm.com/downloads), which includes Git Bash
- A second terminal window for testing the key

MobaXterm is recommended for managing the printer, but the commands below use
Git Bash to create and test the key.

## 1. Create a dedicated key

Open **Git Bash** on your Windows computer and run:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/k2plus_secure_auth -C "k2plus-secure-auth"
```

You may protect the key with a passphrase or press Enter twice to leave the
passphrase blank. If you use a passphrase, you must enter it when using the key.

This creates two files:

- `~/.ssh/k2plus_secure_auth` - private key; keep this secret and backed up
- `~/.ssh/k2plus_secure_auth.pub` - public key; this is copied to the printer

Never send the private key to the printer or share it with anyone.

## 2. Copy the public key to the printer

Replace `192.168.1.239` in these examples with your printer's IP address.

From Git Bash, copy the public key to a temporary file on the printer:

```sh
scp ~/.ssh/k2plus_secure_auth.pub root@192.168.1.239:/tmp/k2plus_secure_auth.pub
```

### If SSH reports that the host identification changed

After an intentional printer wipe, firmware reinstall, or recovery, the
printer may generate a new SSH host key. Git Bash will then stop `scp` with a
`REMOTE HOST IDENTIFICATION HAS CHANGED` warning.

Only when you know the printer was intentionally wiped or reinstalled, remove
its old saved host key from your Windows computer:

```sh
ssh-keygen -R 192.168.1.239
```

Then retry the copy:

```sh
scp ~/.ssh/k2plus_secure_auth.pub root@192.168.1.239:/tmp/k2plus_secure_auth.pub
```

When prompted about the new fingerprint, type `yes`. If the printer was not
intentionally wiped, reinstalled, or recovered, do not remove the saved key.
An unexpected host-key change could mean that you are connecting to a different
device or that the connection is being intercepted; investigate it first.

Accept the host fingerprint if prompted, then enter the printer's current root
password. Password characters are not displayed while you type.

Connect to the printer:

```sh
ssh root@192.168.1.239
```

In that printer SSH session, run:

```sh
mkdir -p /etc/dropbear
chmod 700 /etc/dropbear
touch /etc/dropbear/authorized_keys
cat /tmp/k2plus_secure_auth.pub >> /etc/dropbear/authorized_keys
chmod 600 /etc/dropbear/authorized_keys
rm -f /tmp/k2plus_secure_auth.pub
```

Appending the same public key more than once is harmless, although duplicate
lines may be removed later if desired.

## 3. Keep the original session open

Do not close the printer SSH session used above. It is your recovery session if
the key test fails.

## 4. Test key-only login in a second terminal

Open a **second Git Bash window** and run:

```sh
ssh -i ~/.ssh/k2plus_secure_auth \
  -o IdentitiesOnly=yes \
  -o PreferredAuthentications=publickey \
  -o PasswordAuthentication=no \
  root@192.168.1.239
```

The test succeeds only if a new printer shell opens without requesting the
printer's root password. A prompt for the key's own passphrase is normal.

If it asks for the printer password or refuses the connection, do not install
Secure Auth. Recheck the commands above from the still-open original session.

## 5. Install Secure Auth

After the key-only test succeeds, return to the original printer session and
open the installer menu:

```sh
cd /mnt/UDISK/root/k2-improvements
sh ./menu.sh
```

Choose **Extras**, then **secure-auth**. The installer verifies that a
valid-looking public key exists and requires you to type `SECURE AUTH` before
changing Dropbear. It then disables password authentication, restarts SSH, and
disconnects the current session.

## 6. Reconnect with the key

From Git Bash, reconnect with:

```sh
ssh -i ~/.ssh/k2plus_secure_auth root@192.168.1.239
```

For MobaXterm, edit or create the printer's SSH session, open **Advanced SSH
settings**, enable **Use private key**, and select the Windows file:

```text
C:\Users\YOUR_WINDOWS_NAME\.ssh\k2plus_secure_auth
```

Open a new MobaXterm session to confirm it connects successfully.

## Factory reset warning

Treat `/etc/dropbear/authorized_keys` as erased by a printer factory reset or
firmware recovery. Your private key remains on your Windows computer, but you
must copy its `.pub` file back to the printer, test key-only login again, and
reinstall Secure Auth.
