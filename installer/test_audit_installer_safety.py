#!/usr/bin/env python3

import os
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


class InstallerAuditSafetyTests(unittest.TestCase):
    def test_menu_uses_stale_pid_aware_lock(self):
        source = (ROOT / "menu.sh").read_text(encoding="utf-8")
        self.assertIn("mkdir \"$INSTALLER_LOCK\"", source)
        self.assertIn("kill -0 \"$lock_pid\"", source)
        self.assertIn("trap release_installer_lock EXIT", source)
        self.assertIn("trap 'exit 130' INT", source)
        self.assertIn("trap 'exit 143' TERM", source)
        self.assertIn("trap 'exit 129' HUP", source)

    def test_every_direct_menu_prompt_uses_eof_safe_reader(self):
        prompt_files = [ROOT / "installer/lib/common.sh"]
        prompt_files.extend((ROOT / "installer/menus").glob("*.sh"))
        direct_read = re.compile(r"^\s*read(?:\s+-r)?\s+", re.MULTILINE)
        for path in prompt_files:
            with self.subTest(path=path):
                source = path.read_text(encoding="utf-8")
                self.assertIsNone(direct_read.search(source))

    @unittest.skipUnless(pathlib.Path(BASH).exists(), "bash required")
    def test_closed_input_exits_instead_of_spinning(self):
        script = """
. "$COMMON"
read_prompt choice
printf 'unreachable\\n'
"""
        result = subprocess.run(
            [BASH, "-c", script],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=2,
            env=dict(
                os.environ,
                COMMON=(ROOT / "installer/lib/common.sh").as_posix(),
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installer input closed; exiting", result.stderr)
        self.assertNotIn("unreachable", result.stdout)

    def test_bootstrap_better_root_backs_up_and_targets_only_root(self):
        source = (ROOT / "bootstrap/better-root/install.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("passwd.before-better-root", source)
        self.assertIn("root:[^:]*:[^:]*:[^:]*:[^:]*", source)
        self.assertIn("xargs -r kill -9", source)
        self.assertNotIn("sed -i 's,/root,", source)

    def test_plate_workflow_uses_correct_named_selector_detector(self):
        source = (ROOT / "installer/menus/extras.sh").read_text(
            encoding="utf-8"
        )
        start = source.index("'Named plate selectors'")
        end = source.index("'Surface-selection wrapper'", start)
        self.assertIn("is_carto_macros", source[start:end])

    def test_restore_path_rejects_system_roots(self):
        source = (ROOT / "scripts/restore-path.sh").read_text(encoding="utf-8")
        for path in ("/bin", "/etc", "/lib", "/sbin", "/usr", "/var"):
            self.assertIn(path, source)

    def test_legacy_setup_markers_are_unique_per_run(self):
        for name in ("no-carto.sh", "gimme-the-jamin.sh"):
            source = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("mktemp -d", source)
                self.assertIn("$RUN_MARKERS/${FEATURE}", source)
                self.assertNotIn("/tmp/${FEATURE}", source)

    def test_prtouch_cleanup_removes_the_entire_saved_section(self):
        source = (
            ROOT / "installer/extras/prtouch-cleanup/install.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("skip=1", source)
        self.assertIn("skip && /^#\\*# \\[/ { skip=0 }", source)
        self.assertIn("skip && /^#\\*#/ { next }", source)

    def test_material_editor_preserves_unmanaged_start_print(self):
        source = (
            ROOT / "installer/extras/material-z-offsets/install.sh"
        ).read_text(encoding="utf-8")
        backup = source.index("backup_unmanaged_start_print")
        replace = source.index('ln -sfn "$START_PRINT_SOURCE"')
        self.assertLess(backup, replace)

    def test_start_print_backups_preserve_only_unmanaged_files(self):
        source = (
            ROOT / "installer/lib/start_print_backups.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('[ -L "$candidate" ] && return 0', source)
        self.assertIn('cmp -s "$candidate" "$source_file"', source)
        self.assertIn("BEGIN surface-selection wrapper", source)
        self.assertIn("END surface-selection wrapper", source)
        self.assertIn('cmp -s "$candidate" "$target"', source)
        self.assertIn('rm -f "$candidate"', source)

    def test_plate_aware_installer_requires_python3(self):
        source = (
            ROOT / "installer/extras/plate-aware-mesh/install.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('PYTHON="${K2_PYTHON:-python3}"', source)
        self.assertIn('"$PYTHON" "$SCRIPT_DIR/../../../scripts/ensure_included.py"', source)
        self.assertIn('"$PYTHON" "$SCRIPT_DIR/configure_slicers.py" "$@" --check-only', source)

    def test_memory_diagnostics_migration_has_repair_and_code_restart(self):
        source = (ROOT / "installer/menus/update.sh").read_text(encoding="utf-8")
        self.assertIn("features/memory-diagnostics/install.sh", source)
        restart = source.index("migration_component_restart_kind()")
        self.assertIn("memory-diagnostics", source[restart:])


if __name__ == "__main__":
    unittest.main()
