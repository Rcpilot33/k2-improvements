#!/bin/ash

set -e

SCRIPT_DIR="$(readlink -f $(dirname $0))"
AUTHORIZED_KEYS=/etc/dropbear/authorized_keys

has_public_key() {
    [ -s "$AUTHORIZED_KEYS" ] || return 1
    awk '
        /^[[:space:]]*(#|$)/ { next }
        {
            for (i = 1; i < NF; i++) {
                if ($i ~ /^(ssh-(rsa|dss|ed25519)|ecdsa-sha2-nistp(256|384|521)|sk-ssh-ed25519@openssh.com|sk-ecdsa-sha2-nistp256@openssh.com)$/ &&
                    $(i + 1) ~ /^[A-Za-z0-9+\/=]+$/ && length($(i + 1)) > 20) {
                    found = 1
                }
            }
        }
        END { exit(found ? 0 : 1) }
    ' "$AUTHORIZED_KEYS"
}

if ! has_public_key; then
    echo "ERROR: secure-auth was not installed."
    echo "ERROR: no valid-looking SSH public key was found in $AUTHORIZED_KEYS"
    echo "Add and test a key-based SSH login first; password authentication remains enabled."
    exit 1
fi

echo "I: SSH public key found in $AUTHORIZED_KEYS"
echo "I: make sure key-based login has been tested from another terminal."

echo "Updating dropbear init script to disable password authentication ..."
cp -f "${SCRIPT_DIR}/dropbear.init" /etc/init.d/dropbear
chmod +x /etc/init.d/dropbear

echo "Restarting dropbear..."
/etc/init.d/dropbear restart

echo "Done"

echo "I: you need to log back in for changes to take effect!"
echo "I: logging you out now!"
echo "I: please reconnect to continue"
# terminate the SSH session
pgrep dropbear | grep -v "^$(pgrep -o dropbear)$" | xargs kill -9
