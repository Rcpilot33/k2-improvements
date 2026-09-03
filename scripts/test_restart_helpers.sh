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
        printf '%s\n' post >> "$K2_TEST_POST_MARKER"
        printf '%s\n' '{"result":"ok"}'
        ;;
    *'/printer/objects/query?motor_control'*)
        if [ -n "${K2_TEST_MOTOR_FALSE_COUNT:-}" ]; then
            count_file=$K2_TEST_MOTOR_COUNTER
            count=0
            [ ! -e "$count_file" ] || count=$(cat "$count_file")
            count=$((count + 1))
            printf '%s\n' "$count" > "$count_file"
            if [ "$count" -le "$K2_TEST_MOTOR_FALSE_COUNT" ]; then
                printf '%s\n' '{"motor_ready":false}'
            else
                printf '%s\n' '{"motor_ready":true}'
            fi
        else
            printf '%s\n' "${K2_TEST_MOTOR_JSON:-{\"motor_ready\":true}}"
        fi
        ;;
    *)
        posts=0
        [ ! -e "$K2_TEST_POST_MARKER" ] || posts=$(wc -l < "$K2_TEST_POST_MARKER")
        case "${K2_TEST_SEQUENCE:-fixed}" in
            normal-transitions)
                count_file=$K2_TEST_INFO_COUNTER
                count=0
                [ ! -e "$count_file" ] || count=$(cat "$count_file")
                count=$((count + 1))
                printf '%s\n' "$count" > "$count_file"
                case "$count" in
                    1) printf '%s\n' '{"state":"startup","state_message":"key3"}' ;;
                    2) printf '%s\n' '{}' ;;
                    3) printf '%s\n' '{"state":"startup","state_message":"key3"}' ;;
                    *) printf '%s\n' '{"state":"ready"}' ;;
                esac
                ;;
            persistent-failure)
                if [ "$posts" -eq 1 ]; then
                    printf '%s\n' '{"state":"shutdown","state_message":"key1"}'
                else
                    printf '%s\n' '{"state":"ready"}'
                fi
                ;;
            *)
                if [ "${K2_TEST_READY_AFTER_POST:-0}" = 1 ] && \
                   [ "$posts" -gt 0 ]; then
                    printf '%s\n' '{"state":"ready"}'
                else
                    printf '%s\n' "${K2_TEST_INFO_JSON}"
                fi
                ;;
        esac
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
grep -q 'remained ready for 5 seconds' "$TMP_DIR/ready.out" || \
    fail 'ready path did not complete stabilization'
grep -q 'K2 motor controller are ready' "$TMP_DIR/ready.out" || \
    fail 'pre-reset motor-ready gate was skipped'

# Fluidd's normal disconnect/unknown/key3 startup sequence must not consume a
# recovery attempt. The helper should wait through it and complete one reset.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_TEST_SEQUENCE=normal-transitions \
K2_TEST_INFO_COUNTER="$TMP_DIR/normal.counter" \
K2_TEST_POST_MARKER="$TMP_DIR/normal.post" \
K2_READY_STABLE_SECONDS=2 K2_FIRMWARE_RESTART_ATTEMPTS=2 \
    sh "$REPO_DIR/scripts/firmware_restart.sh" >"$TMP_DIR/normal.out" 2>&1
[ "$(wc -l < "$TMP_DIR/normal.post")" -eq 1 ] || \
    fail 'normal startup transitions incorrectly consumed a recovery attempt'

# A persistent key1-style shutdown should advance to recovery without using
# the full general startup timeout, and the second attempt may still recover.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_TEST_SEQUENCE=persistent-failure \
K2_TEST_POST_MARKER="$TMP_DIR/failure.post" \
K2_FAILURE_GRACE_SECONDS=3 K2_READY_STABLE_SECONDS=2 \
K2_FIRMWARE_RESTART_ATTEMPTS=2 \
    sh "$REPO_DIR/scripts/firmware_restart.sh" >"$TMP_DIR/failure.out" 2>&1
[ "$(wc -l < "$TMP_DIR/failure.post")" -eq 2 ] || \
    fail 'persistent shutdown did not trigger exactly one recovery attempt'
grep -q 'remained in error/shutdown for 3 seconds' "$TMP_DIR/failure.out" || \
    fail 'persistent shutdown was not identified'

# Klippy ready alone is insufficient while the K2 motor controller explicitly
# reports that it is not ready.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_MOTOR_FALSE_COUNT=2 \
K2_TEST_MOTOR_COUNTER="$TMP_DIR/motor.counter" \
K2_TEST_POST_MARKER="$TMP_DIR/motor.post" \
K2_READY_STABLE_SECONDS=2 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    sh "$REPO_DIR/scripts/firmware_restart.sh" >"$TMP_DIR/motor.out" 2>&1
[ "$(cat "$TMP_DIR/motor.counter")" -ge 4 ] || \
    fail 'motor-ready false state did not delay stable completion'

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
