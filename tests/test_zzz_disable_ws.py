import unittest
import importlib
import os
import sys

base_modules = sys.modules.keys()


def _drop_all_speasy_mods():
    keys = list(sys.modules.keys())
    for module in ('pickle', 'sqlite3', 'diskcache', 'speasy'):
        for name in keys:
            if name.startswith(module) or (name not in base_modules):
                if name in sys.modules:
                    sys.modules.pop(name)


class DisableWS(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        os.environ.pop("SPEASY_CORE_DISABLED_PROVIDERS")
        _drop_all_speasy_mods()

    def test_disable_amda(self):
        os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = "amda"
        _drop_all_speasy_mods()
        import speasy as spz
        self.assertNotIn("amda", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.amda)
        self.assertIn("cda", spz.inventories.tree.__dict__)
        self.assertIsNotNone(spz.cda)

    def test_disable_ssc_and_cda(self):
        os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = "ssc,cda"
        _drop_all_speasy_mods()
        import speasy as spz
        self.assertNotIn("ssc", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.ssc)
        self.assertNotIn("cda", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.cda)
        self.assertIn("amda", spz.inventories.tree.__dict__)
        self.assertIsNotNone(spz.amda)


if __name__ == '__main__':
    unittest.main()
