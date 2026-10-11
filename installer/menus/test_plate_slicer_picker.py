"""Both plate workflows use the same picker and installer environment contract."""

import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"


@unittest.skipUnless(Path(BASH).is_file(), "bash required")
class PlatePickerTests(unittest.TestCase):
    def run_picker(self, workflow, answer):
        script = r'''
set -eu
. "$INSTALLER_DIR/installer/menus/extras.sh"
clear() { :; }
ui_heading() { :; }
confirm() { return 0; }
press_enter() { :; }
read_prompt() { read -r "$1"; }
warn() { printf 'WARN:%s\n' "$1"; }
info() { :; }
c_green() { printf '%s' "$1"; }
c_yellow() { printf '%s' "$1"; }
state_installed() { printf INSTALLED; }
state_not_installed() { printf NOT_INSTALLED; }
is_stock_probe() { return 0; }
is_cartographer() { return 0; }
is_carto_macros() { return 0; }
is_surface_wrap() { return 0; }
is_carto_plate_workflow() { return 0; }
is_plate_aware_mesh() { return 1; }
show_feature_readme() { :; }
awk() { printf '/mnt/UDISK/root\n'; }
sh() { printf 'INSTALL:%s:%s\n' "${K2_PLATE_SLICERS:-}" "$1"; }
if [ "$WORKFLOW" = stock ]; then
    run_extra_name plate-aware-mesh
else
    run_carto_plate_workflow
fi
'''
        result = subprocess.run([BASH, "-c", script], input=(answer + "\n").encode(),
                                capture_output=True, timeout=10,
                                env=dict(os.environ, INSTALLER_DIR=ROOT.as_posix(), WORKFLOW=workflow,
                                         K2_PLATE_SLICERS=""))
        return result.returncode, result.stdout.decode(), result.stderr.decode()

    def test_same_three_choices_reach_each_workflow_installer(self):
        for workflow in ("stock", "cartographer"):
            for answer, expected in (("1", "creality"), ("2", "orca"), ("3", "both"), ("", "")):
                with self.subTest(workflow=workflow, answer=answer):
                    code, output, error = self.run_picker(workflow, answer)
                    self.assertEqual(code, 0, error)
                    self.assertIn("1. Creality Print  2. OrcaSlicer  3. Both", output)
                    self.assertIn("INSTALL:%s:" % expected, output)
                    target = "plate-aware-mesh" if workflow == "stock" else "cartographer-macros"
                    self.assertIn(target + "/install.sh", output)

    def test_invalid_choice_runs_no_installer(self):
        for workflow in ("stock", "cartographer"):
            code, output, error = self.run_picker(workflow, "4")
            self.assertNotEqual(code, 0, error)
            self.assertIn("Invalid plate selector choice", output)
            self.assertNotIn("INSTALL:", output)


if __name__ == "__main__":
    unittest.main()
