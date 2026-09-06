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

cat > "$TMP_DIR/bin/curl" <<'EOF'
#!/bin/sh
case " $* " in
    *' -X POST '*)
        : > "$K2_TEST_POST_MARKER"
        printf '%s\n' '{"result":"ok"}'
        ;;
    *'motor_control=motor_ready'*)
        if [ -n "${K2_TEST_MOTOR_JSON:-}" ]; then
            printf '%s\n' "$K2_TEST_MOTOR_JSON"
        else
            printf '%s\n' '{"result":{"status":{"motor_control":{"motor_ready":true}}}}'
        fi
        ;;
    *)
        if [ "${K2_TEST_READY_AFTER_POST:-0}" = 1 ] &&
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
printf '%s\n' "$1" >> "$K2_TEST_SLEEP_LOG"
EOF
cat > "$TMP_DIR/bin/klipper-service" <<'EOF'
#!/bin/sh
[ "$1" = restart ] || exit 1
EOF
chmod +x "$TMP_DIR/bin/curl" "$TMP_DIR/bin/sleep" \
    "$TMP_DIR/bin/klipper-service"

cat > "$TMP_DIR/bin/save-curl" <<'EOF'
#!/bin/sh
case "$*" in
    *motor_control=motor_ready*)
        printf '%s\n' '{"result":{"status":{"motor_control":{"motor_ready":true}}}}'
        ;;
    *printer/info*)
        count=0
        [ ! -f "$K2_TEST_INFO_COUNT" ] || count=$(cat "$K2_TEST_INFO_COUNT")
        count=$((count + 1))
        printf '%s\n' "$count" > "$K2_TEST_INFO_COUNT"
        case "$count" in
            1) printf '%s\n' '{"state":"ready"}' ;;
            2) printf '%s\n' '{"state":"startup"}' ;;
            *) printf '%s\n' '{"state":"ready"}' ;;
        esac
        ;;
    *) exit 1 ;;
esac
EOF
cat > "$TMP_DIR/bin/firmware-helper" <<'EOF'
#!/bin/sh
[ "${K2_FIRMWARE_RESTART_ATTEMPTS:-}" = 1 ] || exit 2
: > "$K2_TEST_FIRMWARE_MARKER"
EOF
cat > "$TMP_DIR/bin/save-error-curl" <<'EOF'
#!/bin/sh
case "$*" in
    *motor_control=motor_ready*)
        printf '%s\n' '{"result":{"status":{"motor_control":{"motor_ready":false}}}}'
        ;;
    *printer/info*)
        count=0
        [ ! -f "$K2_TEST_INFO_COUNT" ] || count=$(cat "$K2_TEST_INFO_COUNT")
        count=$((count + 1))
        printf '%s\n' "$count" > "$K2_TEST_INFO_COUNT"
        case "$count" in
            1) printf '%s\n' '{"state":"ready"}' ;;
            2) printf '%s\n' '{"state":"startup"}' ;;
            *)
                printf '%s\n' "$K2_TEST_ERROR_LINE" >> "$K2_TEST_KLIPPY_LOG"
                printf '%s\n' '{"state":"shutdown","state_message":"{\"code\":\"key1\",\"msg\":\"Internal error during ready callback\"}"}'
                ;;
        esac
        ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$TMP_DIR/bin/save-curl" "$TMP_DIR/bin/save-error-curl" \
    "$TMP_DIR/bin/firmware-helper"

# The ready host path must require motor readiness before and after its one
# firmware restart; it no longer relies on a fixed delay.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_POST_MARKER="$TMP_DIR/ready.post" \
K2_TEST_SLEEP_LOG="$TMP_DIR/ready.sleeps" \
K2_WAIT_FOR_KLIPPY_STARTUP=1 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    sh "$REPO_DIR/scripts/firmware_restart.sh" >"$TMP_DIR/ready.out" 2>&1
grep -q 'K2 motor controller are ready; continuing with one protected firmware reset' \
    "$TMP_DIR/ready.out" || fail 'pre-reset motor readiness was not verified'
[ "$(grep -c '^25$' "$TMP_DIR/ready.sleeps" || true)" -eq 0 ] ||
    fail 'installer still used a fixed 25-second readiness delay'
grep -q 'K2 motor controller reports ready' "$TMP_DIR/ready.out" ||
    fail 'post-reset motor readiness was not verified'

# The installer must request exactly one firmware restart on every firmware.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_KLIPPER_SERVICE="$TMP_DIR/bin/klipper-service" \
K2_PRINTER_FW_OVERRIDE=1.1.3.13 K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_POST_MARKER="$TMP_DIR/old-fw.post" \
K2_TEST_SLEEP_LOG="$TMP_DIR/old-fw.sleeps" \
    sh "$REPO_DIR/scripts/klippy_code_restart.sh" >"$TMP_DIR/old-fw.out" 2>&1
[ "$(grep -c 'requesting FIRMWARE_RESTART through Moonraker' "$TMP_DIR/old-fw.out")" -eq 1 ] ||
    fail 'installer did not use exactly one firmware restart'

# A premature API-ready state with motor_ready=false must stop before reset.
if PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
    K2_KLIPPER_SERVICE="$TMP_DIR/bin/klipper-service" \
    K2_TEST_INFO_JSON='{"state":"ready"}' \
    K2_TEST_MOTOR_JSON='{"result":{"status":{"motor_control":{"motor_ready":false}}}}' \
    K2_TEST_POST_MARKER="$TMP_DIR/failed-start.post" \
    K2_TEST_SLEEP_LOG="$TMP_DIR/failed-start.sleeps" \
    K2_MOTOR_READY_TIMEOUT=2 \
    sh "$REPO_DIR/scripts/klippy_code_restart.sh" \
        >"$TMP_DIR/failed-start.out" 2>&1; then
    fail 'installer accepted API ready while the motor controller was not ready'
fi
[ ! -e "$TMP_DIR/failed-start.post" ] ||
    fail 'installer requested firmware restart before motor readiness'
grep -q 'no firmware restart was requested' "$TMP_DIR/failed-start.out" ||
    fail 'installer failure did not explain the safe stop'

# Runtime SAVE_CONFIG must observe stock restart and motor readiness, then call
# the firmware helper exactly once without restarting the Klippy service.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/save-curl" \
K2_TEST_INFO_COUNT="$TMP_DIR/save.info-count" \
K2_TEST_FIRMWARE_MARKER="$TMP_DIR/save.firmware" \
K2_TEST_SLEEP_LOG="$TMP_DIR/save.sleeps" \
K2_FIRMWARE_RESTART_HELPER="$TMP_DIR/bin/firmware-helper" \
K2_SAVE_CONFIG_TRANSITION_TIMEOUT=5 K2_SAVE_CONFIG_READY_TIMEOUT=5 \
    sh "$REPO_DIR/scripts/save_config_restart.sh" >"$TMP_DIR/save.out" 2>&1
[ -e "$TMP_DIR/save.firmware" ] ||
    fail 'SAVE_CONFIG did not request its one firmware restart'
grep -q 'stock Klipper restart and K2 motor initialization completed' \
    "$TMP_DIR/save.out" || fail 'SAVE_CONFIG skipped readiness gates'

# Only the exact key798 extruder-motor startup fault may invoke recovery.
printf '%s\n' baseline > "$TMP_DIR/recovery.klippy.log"
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/save-error-curl" \
K2_TEST_INFO_COUNT="$TMP_DIR/recovery.info-count" \
K2_TEST_KLIPPY_LOG="$TMP_DIR/recovery.klippy.log" \
K2_KLIPPY_LOG="$TMP_DIR/recovery.klippy.log" \
K2_TEST_ERROR_LINE="!! {\"code\":\"key798\",\"msg\":\"Motor connection failed, exceeding maximum retry count\",\"values\":['e']}" \
K2_TEST_FIRMWARE_MARKER="$TMP_DIR/recovery.firmware" \
K2_TEST_SLEEP_LOG="$TMP_DIR/recovery.sleeps" \
K2_FIRMWARE_RESTART_HELPER="$TMP_DIR/bin/firmware-helper" \
K2_SAVE_CONFIG_TRANSITION_TIMEOUT=5 K2_SAVE_CONFIG_READY_TIMEOUT=5 \
K2_SAVE_CONFIG_MOTOR_E_RECOVERY_DELAY=0 \
    sh "$REPO_DIR/scripts/save_config_restart.sh" \
        >"$TMP_DIR/recovery.out" 2>&1
[ -e "$TMP_DIR/recovery.firmware" ] ||
    fail 'validated key798 motor-e fault did not request recovery'
grep -q 'complete(recovered-motor-e)' /tmp/k2-save-config-restart.status ||
    fail 'validated key798 motor-e recovery was not recorded'

# A different error remains fail-closed and must not invoke the helper.
printf '%s\n' baseline > "$TMP_DIR/other-error.klippy.log"
if PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/save-error-curl" \
    K2_TEST_INFO_COUNT="$TMP_DIR/other-error.info-count" \
    K2_TEST_KLIPPY_LOG="$TMP_DIR/other-error.klippy.log" \
    K2_KLIPPY_LOG="$TMP_DIR/other-error.klippy.log" \
    K2_TEST_ERROR_LINE='!! {"code":"key298","msg":"Can not update MCU rpi config as it is shutdown","values":["rpi"]}' \
    K2_TEST_FIRMWARE_MARKER="$TMP_DIR/other-error.firmware" \
    K2_TEST_SLEEP_LOG="$TMP_DIR/other-error.sleeps" \
    K2_FIRMWARE_RESTART_HELPER="$TMP_DIR/bin/firmware-helper" \
    K2_SAVE_CONFIG_TRANSITION_TIMEOUT=5 K2_SAVE_CONFIG_READY_TIMEOUT=5 \
    K2_SAVE_CONFIG_MOTOR_E_RECOVERY_DELAY=0 \
    sh "$REPO_DIR/scripts/save_config_restart.sh" \
        >"$TMP_DIR/other-error.out" 2>&1; then
    fail 'unrecognized SAVE_CONFIG fault was automatically recovered'
fi
[ ! -e "$TMP_DIR/other-error.firmware" ] ||
    fail 'unrecognized SAVE_CONFIG fault invoked firmware recovery'
grep -q 'failed(stock-error)' /tmp/k2-save-config-restart.status ||
    fail 'unrecognized SAVE_CONFIG fault was not recorded'

echo 'restart helper tests: PASS'
