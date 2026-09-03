#!/bin/sh
set -eu

REPO_DIR=$(cd "$(dirname "$0")/.." && pwd)
TMP_DIR=${TMPDIR:-/tmp}/k2-restart-tests.$$
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM
mkdir -p "$TMP_DIR/bin"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# Mock Moonraker and sleep so startup-state behavior is deterministic and fast.
cat > "$TMP_DIR/bin/curl" <<'EOF'
#!/bin/sh
case " $* " in
    *' -X POST '*)
        : > "$K2_TEST_POST_MARKER"
        printf '%s\n' '{"result":"ok"}'
        ;;
    *)
        if [ "${K2_TEST_READY_AFTER_POST:-0}" = 1 ] && \
           [ -e "$K2_TEST_POST_MARKER" ]; then
            printf '%s\n' '{"state":"ready"}'
        else
            printf '%s\n' "${K2_TEST_INFO_JSON}"
        fi
        ;;
esac
EOF
cat > "$TMP_DIR/bin/sleep" <<'EOF'
#!/bin/sh
exit 0
EOF
cat > "$TMP_DIR/bin/klipper-service" <<'EOF'
#!/bin/sh
[ "$1" = restart ] || exit 1
: > "$K2_TEST_SERVICE_MARKER"
EOF
chmod +x "$TMP_DIR/bin/curl" "$TMP_DIR/bin/sleep" \
    "$TMP_DIR/bin/klipper-service"

# 1.1.3.13 receives a third automatic recovery attempt.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_KLIPPER_SERVICE="$TMP_DIR/bin/klipper-service" \
K2_PRINTER_FW_OVERRIDE=1.1.3.13 K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_POST_MARKER="$TMP_DIR/old-fw.post" \
K2_TEST_SERVICE_MARKER="$TMP_DIR/old-fw.service" \
    sh "$REPO_DIR/scripts/klippy_code_restart.sh" >"$TMP_DIR/old-fw.out" 2>&1
[ -e "$TMP_DIR/old-fw.service" ] || fail 'Klippy service restart was not requested'
grep -q 'attempt 1/3' "$TMP_DIR/old-fw.out" || \
    fail '1.1.3.13 did not receive three recovery attempts'

# A fresh host that enters shutdown must proceed into firmware-reset recovery.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_TEST_INFO_JSON='{"state":"shutdown"}' \
K2_TEST_READY_AFTER_POST=1 \
K2_TEST_POST_MARKER="$TMP_DIR/shutdown.post" \
K2_WAIT_FOR_KLIPPY_STARTUP=1 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    sh "$REPO_DIR/scripts/firmware_restart.sh" >"$TMP_DIR/shutdown.out" 2>&1
[ -e "$TMP_DIR/shutdown.post" ] || \
    fail 'shutdown startup state did not begin firmware-reset recovery'
grep -q 'beginning firmware-reset recovery' "$TMP_DIR/shutdown.out" || \
    fail 'shutdown recovery was not explained'

# A ready fresh host must proceed through the reset and stabilization checks.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_POST_MARKER="$TMP_DIR/ready.post" \
K2_WAIT_FOR_KLIPPY_STARTUP=1 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    sh "$REPO_DIR/scripts/firmware_restart.sh" >"$TMP_DIR/ready.out" 2>&1
[ -e "$TMP_DIR/ready.post" ] || fail 'ready startup state did not request FIRMWARE_RESTART'
grep -q 'motor initialization interval complete' "$TMP_DIR/ready.out" || \
    fail 'ready path did not complete stabilization'
grep -q 'waiting 25 seconds for K2 controller startup before firmware reset' \
    "$TMP_DIR/ready.out" || fail 'pre-reset controller stabilization was skipped'

# Completed repairs remain pending on the same boot, then reconcile only after
# a real reboot and a ready Klipper API response.
(
    MIGRATION_STATE_DIR="$TMP_DIR/migration-state"
    K2_BOOT_ID_FILE="$TMP_DIR/boot-id"
    K2_CURL="$TMP_DIR/bin/curl"
    K2_TEST_INFO_JSON='{"state":"ready"}'
    K2_TEST_POST_MARKER="$TMP_DIR/unused.post"
    PRINTER_CFG_DIR="$TMP_DIR/printer-config"
    INSTALLER_DIR="$REPO_DIR"
    export K2_CURL K2_TEST_INFO_JSON K2_TEST_POST_MARKER
    . "$REPO_DIR/installer/menus/update.sh"

    warn() { :; }
    is_kamp() { return 0; }
    migration_catalog() {
        printf '%s\n' 'test-kamp-restart|kamp-adaptive-purge|is_kamp|test'
    }

    mkdir -p "$MIGRATION_STATE_DIR"
    printf '%s\n' 'kamp-adaptive-purge' > "$MIGRATION_AWAITING_REBOOT"
    printf '%s\n' 'boot-a' > "$MIGRATION_AWAITING_BOOT_ID"
    printf '%s\n' 'boot-a' > "$K2_BOOT_ID_FILE"

    migration_reconcile_after_reboot
    [ -e "$MIGRATION_AWAITING_REBOOT" ] || \
        fail 'same-boot verification was incorrectly accepted'

    printf '%s\n' 'boot-b' > "$K2_BOOT_ID_FILE"
    migration_reconcile_after_reboot
    [ ! -e "$MIGRATION_AWAITING_REBOOT" ] || \
        fail 'post-reboot verification marker was not cleared'
    grep -q '^test-kamp-restart$' "$MIGRATION_COMPLETED" || \
        fail 'post-reboot component migration was not marked complete'
)

echo 'restart helper tests: PASS'
