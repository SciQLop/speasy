import unittest
from unittest.mock import patch
import os
from speasy import config
from io import StringIO
from ddt import ddt, data, unpack
from dateutil.parser import parse as parse_dt
from datetime import datetime


@ddt
class ConfigModule(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_config_entry_has_repr(self):
        self.assertIn("ConfigEntry: AMDA/username", str(config.amda.username))

    @patch('sys.stdout', new_callable=StringIO)
    def test_config_module_shows_entries(self, mock_stdout):
        config.show()
        self.assertIn("ConfigEntry: AMDA/username", mock_stdout.getvalue())

    @data(
        ("hello", None, "hello"),
        ("1e9", float, 1e9),
        ("2019-01-01", parse_dt, datetime(2019, 1, 1))
    )
    @unpack
    def test_get_handles_type_conversion(self, default, ctor, expected):
        my_test_entry = config.ConfigEntry("unit-tests", "from-env", default=default, type_ctor=ctor)
        self.assertEqual(expected, my_test_entry.get())
        config.remove_entry(my_test_entry)

    def test_cfg_entry_call_is_get(self):
        my_test_entry = config.ConfigEntry("unit-tests", "from-env", default="10", type_ctor=int)
        self.assertEqual(10, my_test_entry())
        config.remove_entry(my_test_entry)

    def test_reads_first_from_env(self):
        my_test_entry = config.ConfigEntry("unit-tests", "from-env", "DEFAULT")
        os.environ[my_test_entry.env_var_name] = "VALUE FROM ENV"
        self.assertIn('ENV', my_test_entry.get())
        config.remove_entry(my_test_entry)
        os.environ.pop(my_test_entry.env_var_name)

    def test_returns_default_when_not_set(self):
        my_test_entry = config.ConfigEntry("unit-tests", "default_value", "DEFAULT")
        self.assertEqual("DEFAULT", my_test_entry.get())
        config.remove_entry(my_test_entry)

    def test_returns_set_value_when_set(self):
        my_test_entry = config.ConfigEntry("unit-tests", "default_value", "DEFAULT")
        self.assertEqual("DEFAULT", my_test_entry.get())
        my_test_entry.set("NEW VALUE")
        self.assertEqual("NEW VALUE", my_test_entry.get())
        config.remove_entry(my_test_entry)

    def test_set_doesnt_touch_env_if_entry_is_not_in_env(self):
        my_test_entry = config.ConfigEntry("unit-tests", "default_value", "DEFAULT")
        my_test_entry.set("NEW VALUE")
        self.assertNotIn(my_test_entry.env_var_name, os.environ)
        config.remove_entry(my_test_entry)

    def test_set_updates_env_if_entry_is_in_env(self):
        my_test_entry = config.ConfigEntry("unit-tests", "default_value", "DEFAULT")
        os.environ[my_test_entry.env_var_name] = "VALUE FROM ENV"
        my_test_entry.set("NEW VALUE")
        self.assertEqual(os.environ[my_test_entry.env_var_name], "NEW VALUE")
        config.remove_entry(my_test_entry)
        os.environ.pop(my_test_entry.env_var_name)


if __name__ == '__main__':
    unittest.main()
