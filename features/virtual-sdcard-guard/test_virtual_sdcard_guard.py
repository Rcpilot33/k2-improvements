#!/usr/bin/env python3
"""Tests for the virtual-SD multipart-boundary patch."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("patch_virtual_sdcard.py")
SPEC = importlib.util.spec_from_file_location("virtual_sdcard_guard_patch", MODULE_PATH)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


STOCK_SNIPPET = """VALID_GCODE_EXTS = ['gcode', 'g', 'gco']

class VirtualSD:
    def work_handler(self, eventtime):
        line = lines.pop()
        next_file_position = self.file_position + len(line.encode('utf-8')) + 1
        self.next_file_position = next_file_position
        end_time = interval_end_time = self.reactor.monotonic()
        self.gcode.run_script(line)
"""


class BoundaryPredicateTests(unittest.TestCase):
    def test_observed_lowercase_boundary_at_eof_is_recognized(self):
        line = "--------------------------0dfed932be8a2f6e--\r"
        self.assertTrue(PATCHER.is_terminal_multipart_boundary(line, 43077, 43077))

    def test_observed_uppercase_boundary_at_eof_is_recognized(self):
        line = "--------------------------0E5DECDB71C85D4E--\r"
        self.assertTrue(PATCHER.is_terminal_multipart_boundary(line, 100, 100))

    def test_same_boundary_before_eof_is_not_recognized(self):
        line = "--------------------------0dfed932be8a2f6e--\r"
        self.assertFalse(PATCHER.is_terminal_multipart_boundary(line, 99, 100))

    def test_non_hex_and_short_lines_are_not_recognized(self):
        self.assertFalse(
            PATCHER.is_terminal_multipart_boundary(
                "--------------------------not-a-boundary--\r", 100, 100
            )
        )
        self.assertFalse(
            PATCHER.is_terminal_multipart_boundary(
                "--------------------------deadbeef--\r", 100, 100
            )
        )

    def test_normal_unknown_gcode_is_not_hidden(self):
        self.assertFalse(
            PATCHER.is_terminal_multipart_boundary("FUTURE_COMMAND X1\r", 100, 100)
        )


class PatcherTests(unittest.TestCase):
    def test_ignored_tool_updates_position_before_continue(self):
        source=STOCK_SNIPPET.replace('        self.gcode.run_script(line)',
            '        if self.ignore_t_code(line): continue\n        self.gcode.run_script(line)')
        for source in (source,source.replace('\n','\r\n')):
            patched,changed=PATCHER.patch_text(source)
            self.assertTrue(changed)
            self.assertIn(PATCHER.SKIP_MARKER,patched)
            self.assertIn('self.file_position = self.next_file_position',patched.split(PATCHER.SKIP_MARKER)[1])
            self.assertEqual(PATCHER.patch_text(patched),(patched,False))

    def test_upgrade_existing_guard_and_execute_pause_bookkeeping(self):
        source=STOCK_SNIPPET.replace('        self.gcode.run_script(line)',
            '        if self.ignore_t_code(line): continue\n        self.gcode.run_script(line)')
        old,_=PATCHER.patch_boundary_text(source)
        fixed,_=PATCHER.patch_text(old)
        import io
        # Execute the actual installed skip branch over a T0 + extrusion stream.
        block=fixed[fixed.index('        if self.ignore_t_code(line):'):fixed.index('        self.gcode.run_script(line)')]
        block='\n'.join(line[8:] for line in block.splitlines())
        program='for line in lines:\n    self.next_file_position = self.file_position + len(line.encode("utf-8")) + 1\n'+''.join('    '+line+'\n' for line in block.splitlines())+'    self.file_position = self.next_file_position\n'
        from types import SimpleNamespace
        lines=['T0','G1 X1 E.07616']
        state=SimpleNamespace(file_position=0,next_file_position=0,cmd_from_sd=True,ignore_t_code=lambda line:line=='T0')
        exec(program,dict(self=state,lines=lines))
        data=('\n'.join(lines)+'\nG1 X2\n').encode()
        stream=io.BytesIO(data);stream.seek(state.file_position)
        self.assertEqual(stream.readline(),b'G1 X2\n')
        self.assertFalse(state.cmd_from_sd)

    def test_unsupported_skip_layout_refuses_entire_patch(self):
        with self.assertRaises(ValueError):
            PATCHER.patch_text(STOCK_SNIPPET+'\nif self.ignore_t_code(line):\n    other_operation()\n')

    def test_patch_adds_guard_before_dispatch(self):
        patched, changed = PATCHER.patch_text(STOCK_SNIPPET)
        self.assertTrue(changed)
        self.assertIn(PATCHER.MARKER, patched)
        self.assertLess(
            patched.index("_is_terminal_multipart_boundary("),
            patched.index("self.gcode.run_script(line)"),
        )

    def test_patch_is_idempotent(self):
        once, changed = PATCHER.patch_text(STOCK_SNIPPET)
        self.assertTrue(changed)
        twice, changed = PATCHER.patch_text(once)
        self.assertFalse(changed)
        self.assertEqual(once, twice)

    def test_patch_applies_to_captured_k2_source_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "virtual_sdcard.py"
            target.write_text(STOCK_SNIPPET, encoding="utf-8")
            self.assertEqual(PATCHER.main(["patch", str(target)]), 0)
            self.assertEqual(PATCHER.main(["patch", str(target)]), 2)

    def test_legacy_k2_source_encoding_is_preserved_and_declared(self):
        legacy = STOCK_SNIPPET + "# Chinese comment: \u6253\u5370\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "virtual_sdcard.py"
            target.write_bytes(legacy.encode("gbk"))
            self.assertEqual(PATCHER.main(["patch", str(target)]), 0)
            patched = target.read_bytes().decode("gbk")
            self.assertIn("# -*- coding: gbk -*-", patched.splitlines()[:2])
            self.assertIn("# Chinese comment: \u6253\u5370", patched)


if __name__ == "__main__":
    unittest.main()
