import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('resume_fans',Path(__file__).with_name('patch_resume_fans.py'))
patcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(patcher)
STOCK='''[gcode_macro RESUME_EXTERNAL]
gcode:
  {% if printer['gcode_macro PRINTER_PARAM'].fan2_speed > 0 %}
    {% set s_value = 80 %}
  {% endif %}
  {% if printer['gcode_macro PRINTER_PARAM'].fan0_speed > 0 %}
    {% set s_value_0 = 25 %}
  {% endif %}
  M106 P2 S{s_value} F1
  M106 P0 S{s_value_0} F1
[gcode_macro OTHER]
gcode: untouched
'''


class ResumeFansTests(unittest.TestCase):
    def test_defaults_precede_both_conditions_and_preserve_nonzero_calculations(self):
        text,changed=patcher.patch_text(STOCK)
        self.assertTrue(changed)
        body=text.split('gcode:\n',1)[1].split('[gcode_macro OTHER]')[0]
        self.assertLess(body.index('{% set s_value = 0 %}'),body.index('{% if'))
        self.assertLess(body.index('{% set s_value_0 = 0 %}'),body.index('{% if'))
        added='  '+patcher.MARKER+'\n  {% set s_value = 0 %}\n  {% set s_value_0 = 0 %}\n'
        self.assertEqual(text.replace(added,'',1),STOCK)
        self.assertTrue(text.endswith('[gcode_macro OTHER]\ngcode: untouched\n'))
        self.assertEqual(patcher.patch_text(text),(text,False))

    def test_backup_and_encoding_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'gcode_macro.cfg'
            original=(STOCK+'# 中文\n').encode('gbk');p.write_bytes(original)
            patcher.main(['patch',str(p)]);patcher.main(['patch',str(p)])
            self.assertEqual(p.with_name(p.name+'.before-resume-fan-defaults').read_bytes(),original)
            self.assertIn('# 中文',p.read_bytes().decode('gbk'))

    def test_unknown_section_is_refused(self):
        for text in ('',STOCK.replace('M106 P2 S{s_value} F1','different command')):
            with self.assertRaises(ValueError): patcher.patch_text(text)
