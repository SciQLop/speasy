import unittest
import os
from speasy import config


class ConfigModule(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_reads_firt_from_env(self):
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
