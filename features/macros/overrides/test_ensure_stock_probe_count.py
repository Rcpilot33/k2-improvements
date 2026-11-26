from pathlib import Path
import tempfile
import unittest

from ensure_stock_probe_count import main


class StockProbeCountTests(unittest.TestCase):
    def test_upgrade_and_repair_preserve_user_settings(self):
        for original in (
            "# overrides\n[virtual_sdcard]\nforced_leveling: false\n",
            "[bed_mesh]\r\nspeed: 120\r\n# probe_count: 7, 7\r\n",
            "[bed_mesh]",
        ):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "overrides.cfg"
                path.write_bytes(original.encode())
                main(path)
                updated = path.read_bytes()
                self.assertIn(b"probe_count: 19, 19", updated)
                self.assertEqual(updated.count(b"[bed_mesh]"), 1)
                for line in original.splitlines():
                    self.assertIn(line.encode(), updated)
                if "\r\n" in original:
                    self.assertNotIn(b"\n", updated.replace(b"\r\n", b""))
                main(path)
                self.assertEqual(path.read_bytes(), updated)

    def test_existing_count_is_preserved_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overrides.cfg"
            for original in (b"[bed_mesh]\nprobe_count: 13, 15  # my trial\n",
                             b"[bed_mesh] ; tuning\r\nProbe_Count = 9, 9"):
                path.write_bytes(original)
                main(path)
                self.assertEqual(path.read_bytes(), original)
