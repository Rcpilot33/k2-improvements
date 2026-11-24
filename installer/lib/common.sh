#!/bin/sh
# Shared helpers for the K2 Plus installer. Sourced by menu.sh.

INSTALLER_DIR="${INSTALLER_DIR:-/mnt/UDISK/root/k2-improvements}"
PRINTER_CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
KLIPPER_DIR="${KLIPPER_DIR:-/usr/share/klipper}"

if command -v dialog >/dev/null 2>&1; then
    HAS_DIALOG=1
else
    HAS_DIALOG=0
fi

c_red()    { printf '\033[31m%s\033[0m' "$1"; }
c_green()  { printf '\033[32m%s\033[0m' "$1"; }
c_yellow() { printf '\033[33m%s\033[0m' "$1"; }
c_cyan()   { printf '\033[36m%s\033[0m' "$1"; }
c_dim()    { printf '\033[2m%s\033[0m' "$1"; }

state_installed()     { c_green 'INSTALLED'; }
state_complete()      { c_green 'COMPLETE'; }
state_not_installed() { c_dim 'NOT INSTALLED'; }
state_available()     { c_dim 'AVAILABLE'; }
state_pending()       { c_cyan 'PENDING'; }
state_incomplete()    { c_yellow 'INCOMPLETE'; }
state_requires()      { c_yellow "REQUIRES $1"; }
state_blocked()       { c_yellow 'BLOCKED'; }
state_recovery()      { c_yellow 'RECOVERY'; }
state_destructive()   { c_red 'DESTRUCTIVE'; }

ui_rule() {
    printf '%s\n' '============================================================'
}

ui_heading() {
    ui_rule
    printf ' %s\n' "$(c_cyan "$1")"
    ui_rule
}

ui_menu_item() {
    # number, label, optional state
    if [ -n "${3:-}" ]; then
        printf '  %s. %-42s %s\n' "$1" "$2" "$3"
    else
        printf '  %s. %s\n' "$1" "$2"
    fi
}

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "I: $*"; }
warn() { echo "W: $*" >&2; }

# Only capture setup and core component output. Optional authentication
# prompts and unrelated menu activity stay outside the install transcript.
run_logged_install() (
    local label="$1" directory log status result
    shift
    directory="${PRINTER_CFG_DIR%/*}/logs"
    log="$directory/k2-installer.log"
    if ! mkdir -p "$directory" || ! touch "$log"; then
        warn "Cannot create installer log at $log"
        "$@"
        exit $?
    fi
    status=$(mktemp) || return 1
    trap 'rm -f "$status"' EXIT
    # Keep the previous transcript when the accumulated log exceeds 1 MiB.
    if [ "$(wc -c < "$log")" -ge 1048576 ]; then
        mv -f "$log" "$log.1" || return 1
    fi
    printf 'Installer log: %s\n' "$log"
    (
        trap 'printf "%s\n" "$?" > "$status"' EXIT
        printf '\n--- %s | %s | firmware %s | revision %s ---\n' \
            "$(date)" "$label" "$(detect_printer_fw)" "$(detect_installer_commit)"
        "$@"
    ) 2>&1 | tee -a "$log" || warn "Installer output could not be fully saved to $log"
    result=$(cat "$status")
    [ -n "$result" ] || result=1
    printf '%s finished with exit code %s\n' "$label" "$result" | tee -a "$log"
    return "$result"
)

read_prompt() {
    # A closed SSH terminal makes read fail immediately.  Never return that
    # failure to a caller's menu loop: doing so creates an unbounded redraw and
    # status-detection loop that can exhaust the printer's CPU and memory.
    if IFS= read -r "$@"; then
        return 0
    fi
    printf '\nI: installer input closed; exiting.\n' >&2
    exit 0
}

confirm() {
    printf '%s [y/N]: ' "$1"
    read_prompt ans
    case "$ans" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

press_enter() { printf '\nPress Enter to continue...'; read_prompt _; }

require_root() {
    [ "$(id -u)" = "0" ] || die "must run as root"
}

ensure_path() {
    case ":$PATH:" in
        *:/opt/bin:*) ;;
        *) PATH="/opt/bin:/opt/sbin:$PATH"; export PATH ;;
    esac
}

restart_moonraker_and_wait() {
    /etc/init.d/moonraker restart || return 1
    local count=0
    while ! nc -z 127.0.0.1 7125; do
        if [ "$count" -ge 60 ]; then
            warn 'Moonraker did not return after its restart'
            return 1
        fi
        count=$((count + 1))
        sleep 1
    done
}
