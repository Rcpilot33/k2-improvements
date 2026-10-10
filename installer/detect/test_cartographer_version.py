"""Execute the read-only firmware display detector without a printer."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"
SOURCE = Path(__file__).with_name("cartographer.sh")
ROOT = SOURCE.resolve().parents[2]


@unittest.skipUnless(Path(BASH).exists(), "bash required")
class CartographerVersionTests(unittest.TestCase):
    def detect(self, version, fallback=False, no_tr=False):
        source = SOURCE.read_text()
        if fallback:
            # Use a shell-owned fixture in place of the printer's fixed log path.
            setup = '''
fixture=$(mktemp)
trap 'rm -f "$fixture"' EXIT
export K2_CARTO_VERSION_LOG="$fixture"
printf "Loaded MCU 'cartographer' CARTOGRAPHER V3 6.1.0\\nLoaded MCU 'cartographer' %s\\n" "$TEST_VERSION" > "$fixture"
command() { return 1; }
'''
        else:
            setup = '_detect_carto_version_string() { printf "%s\\n" "$TEST_VERSION"; }\n'
        if no_tr:
            setup += '\ntr() { echo "unexpected tr invocation" >&2; return 127; }\n'
        result = subprocess.run(
            [BASH, "-c", source + "\n" + setup + "detect_carto_hw; detect_carto_fw"],
            env=dict(os.environ, TEST_VERSION=version), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("unexpected tr invocation", result.stderr)
        return result.stdout.splitlines()

    def test_supplied_metadata_including_empty_never_queries_again(self):
        script = SOURCE.read_text() + '''
set -u
_detect_carto_version_string() { echo unexpected >&2; return 99; }
detect_carto_hw 'CARTOGRAPHER v4 6.2.0 Lite'
detect_carto_fw 'CARTOGRAPHER v4 6.2.0 Lite'
detect_carto_hw ''
detect_carto_fw ''
'''
        result = subprocess.run([BASH, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ['V4', '6.2.0 (Lite)', 'unknown', 'unknown'])
        self.assertEqual(result.stderr, '')

    def test_unavailable_standalone_lookup_is_unknown_under_strict_shell(self):
        script = SOURCE.read_text() + '''
set -eu
_detect_carto_version_string() { return 1; }
detect_carto_hw
detect_carto_fw
'''
        result = subprocess.run([BASH, '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['unknown', 'unknown'])

    def test_large_single_line_log_is_byte_bounded(self):
        for location in ('header', 'tail', 'middle', 'absent'):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                log = base / 'klippy.log'
                version = b'CARTOGRAPHER v4 6.2.0 Lite\n'
                # Huge lines defeat line-count limits; the middle must never
                # reach grep. A recent record takes priority over startup data.
                log.write_bytes(
                    (version if location == 'header' else b'CARTOGRAPHER V3 5.1.0\n'
                     if location == 'tail' else b'') + b'x' * (6 * 1024 * 1024) + b'\n' +
                    (version if location == 'middle' else b'') +
                    b'x' * (6 * 1024 * 1024) + b'\n' +
                    (version if location == 'tail' else b''))
                script = SOURCE.read_text() + '''
command() { return 1; }
grep() {
    local sample
    sample=$(mktemp)
    cat > "$sample"
    wc -c < "$sample" >> "$READ_COUNTS"
    builtin command grep "$@" < "$sample"
    rm -f "$sample"
}
_detect_carto_version_string || true
'''
                counts = base / 'counts'
                result = subprocess.run([BASH, '-c', script], capture_output=True,
                    text=True, timeout=10, env=dict(os.environ,
                        K2_CARTO_VERSION_LOG=log.as_posix(), READ_COUNTS=counts.as_posix()))
                self.assertEqual(result.returncode, 0, result.stderr)
                sizes = [int(value) for value in counts.read_text().splitlines()]
                self.assertTrue(all(size <= 262144 for size in sizes), sizes)
                self.assertEqual(len(sizes), 1 if location == 'tail' else 2)
                self.assertEqual(result.stdout.strip(),
                    'CARTOGRAPHER v4 6.2.0 Lite' if location in ('header', 'tail') else '')

    def test_live_api_takes_priority_without_reading_log(self):
        script = SOURCE.read_text() + '''
command() { case "$2" in curl|jq) printf '%s\\n' "$2";; *) return 1;; esac; }
curl() { printf '%s\\n' "$*" >&2; echo live-json; }
jq() { cat >/dev/null; echo 'CARTOGRAPHER v4 6.2.0'; }
tail() { echo unexpected-log-read >&2; return 99; }
head() { echo unexpected-log-read >&2; return 99; }
version=$(_detect_carto_version_string)
unset -f tail head
detect_carto_hw "$version"
detect_carto_fw "$version"
'''
        result = subprocess.run([BASH, '-c', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['V4', '6.2.0 (Full)'])
        # curl stderr is suppressed by the production function; no log access.
        self.assertEqual(result.stderr, '')

    def test_empty_live_api_falls_back_and_keeps_two_second_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'klippy.log').write_text('CARTOGRAPHER v4 6.2.0 Lite\n')
            script = SOURCE.read_text() + '''
set -u
command() { case "$2" in curl|jq) printf '%s\\n' "$2";; *) return 1;; esac; }
curl() { printf '%s\\n' "$*" >> "$CURL_CALLS"; echo empty-mcu; }
jq() { cat >/dev/null; }
version=$(_detect_carto_version_string)
detect_carto_hw "$version"
detect_carto_fw "$version"
'''
            result = subprocess.run([BASH, '-c', script], capture_output=True, text=True,
                timeout=5, env=dict(os.environ, CURL_CALLS=(base / 'curl').as_posix(),
                    K2_CARTO_VERSION_LOG=(base / 'klippy.log').as_posix()))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ['V4', '6.2.0 (Lite)'])
            calls = (base / 'curl').read_text().splitlines()
            self.assertEqual(len(calls), 1)
            self.assertIn('--max-time 2', calls[0])

    def test_status_and_probe_tools_share_one_lookup_per_panel(self):
        for panel in ('show_status', 'menu_cartographer_tools'):
            with self.subTest(panel=panel), tempfile.TemporaryDirectory() as directory:
                counts = Path(directory) / 'calls'
                script = '''
set -eu
. "$DETECT_SCRIPT"
. "$STATUS_SCRIPT"
. "$WORKFLOW_SCRIPT"
_detect_carto_version_string() {
    echo lookup >> "$LOOKUPS"
    echo 'CARTOGRAPHER v4 6.2.0 Lite'
}
clear() { :; }
detect_printer_fw() { echo 1.1.7.0; }
detect_install_profile() { echo Cartographer; }
detect_carto_usb_state() { echo 'not detected'; }
detect_carto_offset_label() { echo JimmyV; }
is_cartographer() { return 0; }
is_carto_plate_workflow() { return 1; }
is_surface_wrap() { return 1; }
is_prtouch_clean() { return 0; }
ui_heading() { :; }
ui_menu_item() { :; }
status_line() { :; }
press_enter() { :; }
read_prompt() { c=0; }
c_cyan() { printf '%s' "$1"; }
c_green() { printf '%s' "$1"; }
c_yellow() { printf '%s' "$1"; }
state_installed() { echo installed; }
state_not_installed() { echo not-installed; }
state_available() { echo available; }
state_complete() { echo complete; }
state_requires() { echo required; }
state_recovery() { echo recovery; }
migration_pending_component_count() { echo 0; }
"$PANEL"
'''
                result = subprocess.run([BASH, '-c', script], capture_output=True, text=True,
                    timeout=5, env=dict(os.environ, DETECT_SCRIPT=SOURCE.as_posix(),
                        STATUS_SCRIPT=(ROOT / 'installer/menus/status.sh').as_posix(),
                        WORKFLOW_SCRIPT=(ROOT / 'installer/menus/workflows.sh').as_posix(),
                        INSTALLER_DIR=directory, LOOKUPS=counts.as_posix(), PANEL=panel))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(counts.read_text().splitlines(), ['lookup'])
                self.assertIn('V4', result.stdout)
                self.assertIn('6.2.0 (Lite)', result.stdout)

    def test_live_versions(self):
        for version, expected in (
            ("CARTOGRAPHER V3 6.1.0 lite", ["V3", "6.1.0 (Lite)"]),
            ("CARTOGRAPHER V3 6.1.0", ["V3", "6.1.0 (Full)"]),
            ("CARTOGRAPHER 5.1.0", ["V3", "5.1.0 (Full)"]),
            ("CARTOGRAPHER K1 5.1.0", ["V3", "5.1.0 (Lite)"]),
            ("CARTOGRAPHER V4 6.0.0", ["V4", "6.0.0 (Full)"]),
            ("CARTOGRAPHER v4 6.2.0 Lite", ["V4", "6.2.0 (Lite)"]),
            ("CARTOGRAPHER v4 6.2.0", ["V4", "6.2.0 (Full)"]),
            ("", ["unknown", "unknown"]),
        ):
            with self.subTest(version=version):
                self.assertEqual(self.detect(version), expected)

    def test_log_fallback_preserves_latest_lite_suffix(self):
        self.assertEqual(
            self.detect("CARTOGRAPHER V3 6.1.0 lite", fallback=True),
            ["V3", "6.1.0 (Lite)"],
        )

    def test_hardware_detection_without_tr(self):
        for hardware in ('V3', 'v3', 'V4', 'v4'):
            with self.subTest(hardware=hardware):
                self.assertEqual(
                    self.detect(f'CARTOGRAPHER {hardware} 6.2.0', no_tr=True),
                    [hardware.upper(), '6.2.0 (Full)'],
                )

    def test_lowercase_v4_log_fallback_without_tr(self):
        self.assertEqual(
            self.detect('CARTOGRAPHER v4 6.2.0 Lite', fallback=True, no_tr=True),
            ['V4', '6.2.0 (Lite)'],
        )


if __name__ == "__main__":
    unittest.main()
