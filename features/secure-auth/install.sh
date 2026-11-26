#!/bin/ash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTHORIZED_KEYS=/etc/dropbear/authorized_keys
service=/etc/init.d/dropbear
backup=/etc/dropbear/before-secure-auth.init
factory=/rom/etc/init.d/dropbear
marker='# k2-improvements: secure-auth installed'

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

action=${1:-install}
case "$action" in
    install|--restore) ;;
    *) echo "Usage: $0 [--restore]" >&2; exit 1 ;;
esac

if [ "$action" = install ] && ! has_public_key; then
    echo "ERROR: secure-auth was not installed."
    echo "ERROR: no valid-looking SSH public key was found in $AUTHORIZED_KEYS"
    echo "Add and test a key-based SSH login first; password authentication remains enabled."
    exit 1
fi

[ -f "$service" ] && [ -x "$service" ] || { echo "Missing Dropbear startup script" >&2; exit 1; }
source_script="$SCRIPT_DIR/dropbear.init"
if [ "$action" = --restore ]; then
    if ! grep -Fq "$marker" "$service"; then
        echo "Secure Auth is already disabled."
        exit 0
    fi
    source_script="$backup"
    [ -e "$source_script" ] || source_script="$factory"
    if [ ! -s "$source_script" ] || [ ! -x "$source_script" ] || grep -Fq "$marker" "$source_script"; then
        echo "No original Dropbear startup script available for recovery." >&2
        exit 1
    fi
fi

# Stage under /etc so the live script can be replaced by rename.
work=$(mktemp -d /etc/.secure-auth.XXXXXX)
cleanup() {
    rm -f "$work/previous" "$work/backup" "$work/next"
    rmdir "$work"
}
trap cleanup EXIT
cp -p "$service" "$work/previous"
if [ "$action" = install ] && ! grep -Fq "$marker" "$work/previous"; then
    cp -p "$work/previous" "$work/backup"
    mv -f "$work/backup" "$backup"
fi
cp -p "$source_script" "$work/next"
if [ "$action" = install ]; then chmod 755 "$work/next"; fi
sh -n "$work/next"
mv -f "$work/next" "$service"

# Capture connected clients before restarting. A new listener can have a
# newer PID than an existing session.
clients=''
if [ "$action" = install ]; then
    for pid in $(pidof dropbear); do
        clients="$clients $(pgrep -P "$pid" -x dropbear || :)"
    done
fi
if ! "$service" restart; then
    echo "Dropbear restart failed. Restoring the previous startup script." >&2
    mv -f "$work/previous" "$service"
    "$service" restart || echo "Dropbear could not restart with the previous script." >&2
    exit 1
fi
cleanup
trap - EXIT
if [ "$action" = --restore ]; then
    echo "Restored the original Dropbear startup script."
else
    echo "Secure Auth installed. Reconnect with your SSH key."
    for pid in $clients; do
        [ "$(cat "/proc/$pid/comm" 2>/dev/null)" = dropbear ] && kill -KILL "$pid" || :
    done
fi
