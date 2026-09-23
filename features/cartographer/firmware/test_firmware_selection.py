"""Exercise firmware selection without USB access or importing the flasher."""
import ast
import hashlib
from pathlib import Path
import pathlib
import re
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
                 ('prompt_firmware', 'scan_flash_for_version', '_print_unsupported_device',
                  'v4_620_plugin_supported', 'format_firmware_label')
                 or isinstance(n, ast.Assign) and any(
                     isinstance(t, ast.Name) and t.id in ('V3_610_CHECKSUMS', 'V4_620_CHECKSUMS')
                     for t in n.targets)]
        self.env = dict(pathlib=pathlib, Optional=Optional, hashlib=hashlib, re=re,
                        struct=struct, __file__=str(ROOT / 'flash.py'))
        for name in ('console', 'Text', 'Panel', 'Table', 'box', 'Prompt'):
            self.env[name] = MagicMock()
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'flash.py', 'exec'), self.env)

    def choose(self, choice, mcu='stm32f042x6'):
        self.env['Prompt'].ask.return_value = choice
        return self.env['prompt_firmware'](mcu, 'USB', '5.1.0')

    def test_new_v3_defaults_and_legacy_choices(self):
        self.assertEqual(self.choose('').name,
                         'CartographerV3_6.1.0_USB_full_8kib_offset.bin')
        self.assertEqual(self.choose('2').name,
                         'CartographerV3_6.1.0_USB_lite_8kib_offset.bin')
        self.assertEqual(self.choose('3'), 'ABORT')
        self.assertEqual(self.choose('4').name, 'Survey_Cartographer_USB_8kib_offset.bin')
        self.assertEqual(self.choose('5').name,
                         'Survey_Cartographer_K1_USB_8kib_offset.bin')

        rows = [call.args for call in
                self.env['Table'].return_value.add_row.call_args_list[-5:]]
        self.assertEqual(rows[0][1], 'V3 6.1.0 Full')
        self.assertIn('Recommended', rows[0][2])
        self.assertEqual(rows[1][1], 'V3 6.1.0 Lite')
        self.assertIn('conservative', rows[1][2])
        self.assertEqual(rows[3][1], 'V3 5.1.0 Full')
        self.assertIn('Legacy rollback', rows[3][2])
        self.assertEqual(rows[4][1], 'V3 5.1.0 Lite')
        self.assertIn('Legacy', rows[4][2])

    def test_new_images_and_embedded_hardware_version(self):
        for choice, variant in [('1', 'full'), ('2', 'lite')]:
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
            self.assertIsNone(self.choose('1'))
        with patch.object(Path, 'is_file', return_value=False):
            self.assertIsNone(self.choose('2'))

    def test_v4_and_unsupported_hardware(self):
        self.env['v4_620_plugin_supported'] = lambda: True
        self.assertEqual(self.choose('1', 'stm32g431xx').name,
                         'CartographerV4_6.2.0_USB_full_8kib_offset.bin')
        self.assertEqual(self.env['Prompt'].ask.call_args.kwargs['choices'], ['', '1', '2', '3', '4', '5'])
        self.assertEqual(self.choose('', 'stm32g431xx').name,
                         'CartographerV4_6.2.0_USB_full_8kib_offset.bin')
        self.assertEqual(self.choose('4', 'stm32g431xx').name,
                         'CartographerV4_6.0.0_USB_full_8kib_offset.bin')
        self.assertEqual(self.choose('5', 'stm32g431xx').name,
                         'CartographerV4_6.0.0_USB_lite_8kib_offset.bin')

        rows = [call.args for call in
                self.env['Table'].return_value.add_row.call_args_list[-5:]]
        self.assertEqual(rows[0][1], 'V4 6.2.0 Full')
        self.assertIn('Recommended', rows[0][2])
        self.assertEqual(rows[1][1], 'V4 6.2.0 Lite')
        self.assertIn('conservative', rows[1][2])
        self.assertEqual(rows[3][1], 'V4 6.0.0 Full')
        self.assertIn('Legacy rollback', rows[3][2])
        self.assertEqual(rows[4][1], 'V4 6.0.0 Lite')
        self.assertIn('Legacy', rows[4][2])
        self.assertEqual(self.choose('3', 'stm32g431xx'), 'ABORT')
        self.assertIsNone(self.choose('4', 'unknown'))

    def test_v4_620_requires_audited_plugin(self):
        with patch.object(Path, 'read_bytes', side_effect=FileNotFoundError):
            self.assertFalse(self.env['v4_620_plugin_supported']())
        with patch.object(Path, 'read_bytes', return_value=b'old plugin'):
            self.assertFalse(self.env['v4_620_plugin_supported']())
        self.env['v4_620_plugin_supported'] = lambda: False
        for choice in ('1', '2'):
            self.assertIsNone(self.choose(choice, 'stm32g431xx'))

    def test_v4_620_images_and_version_detection(self):
        self.env['v4_620_plugin_supported'] = lambda: True
        for choice, variant in [('1', 'full'), ('2', 'lite')]:
            path = self.choose(choice, 'stm32g431xx')
            self.assertEqual(path.name, f'CartographerV4_6.2.0_USB_{variant}_8kib_offset.bin')
            data = path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), self.env['V4_620_CHECKSUMS'][path.name])
            flasher = MagicMock(block_size=64, app_start_addr=0x08002000)
            def read_block(command, payload, **kwargs):
                offset = struct.unpack('<I', payload)[0] - flasher.app_start_addr
                return payload + data[offset:offset + 64]
            flasher.send_command.side_effect = read_block
            info = self.env['scan_flash_for_version'](flasher, 'stm32g431xx')
            self.assertEqual(info['version'], 'CARTOGRAPHER v4 6.2.0' + (' Lite' if variant == 'lite' else ''))
            self.assertEqual(info['config']['MCU'], 'stm32g431xx')
            self.assertEqual(info['config']['CARTOGRAPHER_SENSOR_FREQ_DIVISOR'], 8)
        with patch.object(Path, 'read_bytes', return_value=b'corrupt'):
            self.assertIsNone(self.choose('1', 'stm32g431xx'))
        with patch.object(Path, 'is_file', return_value=False):
            self.assertIsNone(self.choose('2', 'stm32g431xx'))

    def test_current_firmware_variant_label_is_explicit(self):
        formatter = self.env['format_firmware_label']
        self.assertEqual(formatter('CARTOGRAPHER v4 6.2.0'),
                         'CARTOGRAPHER v4 6.2.0 (Full)')
        self.assertEqual(formatter('CARTOGRAPHER v4 6.2.0 Lite'),
                         'CARTOGRAPHER v4 6.2.0 (Lite)')


if __name__ == '__main__':
    unittest.main()
