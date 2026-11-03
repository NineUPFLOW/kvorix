import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

fake = types.ModuleType('fd6551')
fake.FD6551 = lambda: (_ for _ in ()).throw(AssertionError('GPIO access forbidden'))
with patch.dict(sys.modules, {'fd6551': fake}):
    spec = importlib.util.spec_from_file_location('panel_test', "/usr/local/lib/front-panel/front-panel.py")
    panel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(panel)

class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(panel.validate_config({})['brightness'], 7)

    def test_existing_config(self):
        value = {'screens':['clock','temp','cpu','ram','node'], 'seconds':5, 'brightness':7, 'icons':True}
        self.assertEqual(panel.validate_config(value)['screens'], value['screens'])

    def test_empty_list(self):
        self.assertEqual(panel.validate_config({'screens':[]})['screens'], ['clock'])

    def test_invalid_types(self):
        for value in [None, [], 'bad', 123, True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                panel.validate_config(value)

    def test_invalid_fields(self):
        for key, values in {'screens':[None, 'clock', [None], ['bad'], ['clock']*33],
                            'brightness':[None, '7', -1, 8, True, 1.5],
                            'seconds':[None, '5', 0, -1, True, float('inf')],
                            'night':[None, 'false', 1]}.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    panel.validate_config({key:value})

    def test_defaults_not_mutated(self):
        value = panel.validate_config({})
        value['screens'].clear()
        self.assertTrue(panel.DEFAULT['screens'])

    def test_encoding(self):
        self.assertEqual(len(panel.encode('1234', False)), 5)
        self.assertEqual(panel.encode('1234', True)[2] ^ panel.encode('1234', False)[2], 128)

    def test_known_screens(self):
        for screen in panel.SCREENS:
            self.assertEqual(panel.validate_config({'screens':[screen]})['screens'], [screen])

if __name__ == '__main__':
    unittest.main(verbosity=2)
