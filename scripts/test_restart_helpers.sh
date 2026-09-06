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

# The ready host path must wait through the full pre-reset controller window.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_POST_MARKER="$TMP_DIR/ready.post" \
K2_TEST_SLEEP_LOG="$TMP_DIR/ready.sleeps" \
K2_WAIT_FOR_KLIPPY_STARTUP=1 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    sh "$REPO_DIR/scripts/firmware_restart.sh" >"$TMP_DIR/ready.out" 2>&1
grep -q 'waiting 25 seconds for K2 controller startup before firmware reset' \
    "$TMP_DIR/ready.out" || fail 'pre-reset controller stabilization was skipped'
[ "$(grep -c '^25$' "$TMP_DIR/ready.sleeps")" -eq 2 ] ||
    fail 'expected both pre-reset and post-reset 25-second waits'

# Firmware 1.1.3.13 must receive a third automatic recovery attempt.
PATH="$TMP_DIR/bin:$PATH" K2_CURL="$TMP_DIR/bin/curl" \
K2_KLIPPER_SERVICE="$TMP_DIR/bin/klipper-service" \
K2_PRINTER_FW_OVERRIDE=1.1.3.13 K2_TEST_INFO_JSON='{"state":"ready"}' \
K2_TEST_POST_MARKER="$TMP_DIR/old-fw.post" \
K2_TEST_SLEEP_LOG="$TMP_DIR/old-fw.sleeps" \
    sh "$REPO_DIR/scripts/klippy_code_restart.sh" >"$TMP_DIR/old-fw.out" 2>&1
grep -q 'attempt 1/3' "$TMP_DIR/old-fw.out" ||
    fail '1.1.3.13 did not receive three recovery attempts'

echo 'restart helper tests: PASS'
