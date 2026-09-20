"""Exercise the host shutdown method without importing firmware modules."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock


class ShutdownDisconnectTests(unittest.TestCase):
    def test_disconnected_shutdown_skips_serial_but_connected_shutdown_is_preserved(self):
        root = Path(__file__).resolve().parents[2]
        for path in (
            root / "features/cartographer/patches/mcu.py",
            root / "installer/scripts/jacob-overlay/features/cartographer/patches/mcu.py",
        ):
            tree = ast.parse(path.read_text())
            cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MCU")
            method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_shutdown")
            namespace = {}
            exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), namespace)
            for disconnected in (False, True):
                for force in (False, True):
                    for already_shutdown in (False, True):
                        with self.subTest(path=path, disconnected=disconnected, force=force,
                                          already_shutdown=already_shutdown):
                            host = Mock(non_critical_disconnected=disconnected, _is_shutdown=already_shutdown)
                            namespace["_shutdown"](host, force=force)
                            if disconnected or (already_shutdown and not force):
                                host._emergency_stop_cmd.send.assert_not_called()
                            else:
                                host._emergency_stop_cmd.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
