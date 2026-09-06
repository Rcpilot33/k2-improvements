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
            printf '%s\n' "$K2_TEST_INFO_JSON"
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

# A normal installer reload must verify motor readiness both before and after
# exactly one firmware restart.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_KLIPPER_SERVICE="$TMP_DIR/bin/klipper-service" \
K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_POST_MARKER="$TMP_DIR/ready.post" \
K2_TEST_SLEEP_LOG="$TMP_DIR/ready.sleeps" \
    sh "$REPO_DIR/scripts/klippy_code_restart.sh" >"$TMP_DIR/ready.out" 2>&1
[ "$(grep -c 'requesting FIRMWARE_RESTART through Moonraker' "$TMP_DIR/ready.out")" -eq 1 ] ||
    fail 'installer did not request exactly one firmware restart'
grep -q 'K2 motor controller are ready; continuing with one protected firmware reset' \
    "$TMP_DIR/ready.out" || fail 'pre-reset motor readiness was not verified'
grep -q 'K2 motor controller reports ready' "$TMP_DIR/ready.out" ||
    fail 'post-reset motor readiness was not verified'

# Klipper API readiness alone must never permit the firmware reset.
if PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
    K2_KLIPPER_SERVICE="$TMP_DIR/bin/klipper-service" \
    K2_TEST_INFO_JSON='{"state":"ready"}' \
    K2_TEST_MOTOR_JSON='{"result":{"status":{"motor_control":{"motor_ready":false}}}}' \
    K2_TEST_POST_MARKER="$TMP_DIR/not-ready.post" \
    K2_TEST_SLEEP_LOG="$TMP_DIR/not-ready.sleeps" \
    K2_MOTOR_READY_TIMEOUT=2 \
    sh "$REPO_DIR/scripts/klippy_code_restart.sh" \
        >"$TMP_DIR/not-ready.out" 2>&1; then
    fail 'installer accepted API ready while motors were not ready'
fi
[ ! -e "$TMP_DIR/not-ready.post" ] ||
    fail 'installer requested firmware restart before motor readiness'
grep -q 'no firmware restart was requested' "$TMP_DIR/not-ready.out" ||
    fail 'safe stop did not explain that no reset was requested'

# An explicit startup fault must also stop before the firmware-reset request.
if PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
    K2_KLIPPER_SERVICE="$TMP_DIR/bin/klipper-service" \
    K2_TEST_INFO_JSON='{"state":"shutdown"}' \
    K2_TEST_POST_MARKER="$TMP_DIR/shutdown.post" \
    K2_TEST_SLEEP_LOG="$TMP_DIR/shutdown.sleeps" \
    K2_MOTOR_READY_TIMEOUT=2 \
    sh "$REPO_DIR/scripts/klippy_code_restart.sh" \
        >"$TMP_DIR/shutdown.out" 2>&1; then
    fail 'installer continued after a startup shutdown'
fi
[ ! -e "$TMP_DIR/shutdown.post" ] ||
    fail 'installer requested firmware restart after a startup shutdown'

echo 'restart helper tests: PASS'
