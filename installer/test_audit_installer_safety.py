#!/usr/bin/env python3

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class InstallerAuditSafetyTests(unittest.TestCase):
    def test_menu_uses_stale_pid_aware_lock(self):
        source = (ROOT / "menu.sh").read_text(encoding="utf-8")
        self.assertIn("mkdir \"$INSTALLER_LOCK\"", source)
        self.assertIn("kill -0 \"$lock_pid\"", source)
        self.assertIn("trap release_installer_lock", source)

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

    def test_material_editor_backs_up_regular_start_print(self):
        source = (
            ROOT / "installer/extras/material-z-offsets/install.sh"
        ).read_text(encoding="utf-8")
        backup = source.index("start_print.cfg.before-material-z-offsets")
        replace = source.index('ln -sfn "$START_PRINT_SOURCE"')
        self.assertLess(backup, replace)

    def test_plate_aware_installer_requires_python3(self):
        source = (
            ROOT / "installer/extras/plate-aware-mesh/install.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('python3 "$SCRIPT_DIR/../../../scripts/ensure_included.py"', source)

    def test_memory_diagnostics_migration_has_repair_and_code_restart(self):
        source = (ROOT / "installer/menus/update.sh").read_text(encoding="utf-8")
        self.assertIn("features/memory-diagnostics/install.sh", source)
        restart = source.index("migration_component_restart_kind()")
        self.assertIn("memory-diagnostics", source[restart:])


if __name__ == "__main__":
    unittest.main()
