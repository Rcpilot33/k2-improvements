"""Exercise firmware selection without USB access or importing the flasher."""
import ast
import hashlib
from pathlib import Path
import pathlib
import struct
from typing import Optional
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parent


class FirmwareSelectionTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'flash.py').read_text(encoding='utf-8'))
        nodes = [n for n in tree.body if
                 isinstance(n, ast.FunctionDef) and n.name in
                 ('prompt_firmware', 'scan_flash_for_version', '_print_unsupported_device')
                 or isinstance(n, ast.Assign) and any(
                     isinstance(t, ast.Name) and t.id == 'V3_610_CHECKSUMS'
                     for t in n.targets)]
        self.env = dict(pathlib=pathlib, Optional=Optional, hashlib=hashlib,
                        struct=struct, __file__=str(ROOT / 'flash.py'))
        for name in ('console', 'Text', 'Panel', 'Table', 'box', 'Prompt'):
            self.env[name] = MagicMock()
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'flash.py', 'exec'), self.env)

    def choose(self, choice, mcu='stm32f042x6'):
        self.env['Prompt'].ask.return_value = choice
        return self.env['prompt_firmware'](mcu, 'USB', '5.1.0')

    def test_existing_choices_preserved(self):
        self.assertEqual(self.choose('').name, 'Survey_Cartographer_USB_8kib_offset.bin')
        self.assertEqual(self.choose('2').name, 'Survey_Cartographer_K1_USB_8kib_offset.bin')
        self.assertEqual(self.choose('3'), 'ABORT')

    def test_new_images_and_embedded_hardware_version(self):
        for choice, variant in [('4', 'full'), ('5', 'lite')]:
            path = self.choose(choice)
            self.assertEqual(path.name, f'CartographerV3_6.1.0_USB_{variant}_8kib_offset.bin')
            data = path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), self.env['V3_610_CHECKSUMS'][path.name])
            flasher = MagicMock(block_size=64, app_start_addr=0x08002000)
            def read_block(command, payload, **kwargs):
                offset = struct.unpack('<I', payload)[0] - flasher.app_start_addr
                return payload + data[offset:offset + 64]
            flasher.send_command.side_effect = read_block
            info = self.env['scan_flash_for_version'](flasher, 'stm32f042x6')
            self.assertIn('6.1.0', info['version'])
            self.assertEqual(info['config']['MCU'], 'stm32f042x6')

    def test_corrupt_or_missing_image_refused(self):
        with patch.object(Path, 'read_bytes', return_value=b'corrupted'):
            self.assertIsNone(self.choose('4'))
        with patch.object(Path, 'is_file', return_value=False):
            self.assertIsNone(self.choose('5'))

    def test_v4_and_unsupported_hardware(self):
        self.assertEqual(self.choose('1', 'stm32g431xx').name,
                         'CartographerV4_6.0.0_USB_full_8kib_offset.bin')
        self.assertEqual(self.env['Prompt'].ask.call_args.kwargs['choices'], ['', '1', '2', '3'])
        self.assertIsNone(self.choose('4', 'unknown'))


if __name__ == '__main__':
    unittest.main()
