import unittest
import importlib
import os
import sys


def _reload_all_speazy_mods():
    keys = list(sys.modules.keys())
    for name in keys:
        if any(map(name.startswith, ('speasy', 'diskcache', 'pickle'))):
            sys.modules[name] = importlib.reload(sys.modules[name])


class DisableWS(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        os.environ.pop("SPEASY_CORE_DISABLED_PROVIDERS")
        _reload_all_speazy_mods()

    def test_disable_amda(self):
        os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = "amda"
        _reload_all_speazy_mods()
        import speasy as spz
        self.assertNotIn("amda", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.amda)
        self.assertIn("cda", spz.inventories.tree.__dict__)
        self.assertIsNotNone(spz.cda)

    def test_disable_ssc_and_cda(self):
        os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = "ssc,cda"
        _reload_all_speazy_mods()
        import speasy as spz
        self.assertNotIn("ssc", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.ssc)
        self.assertNotIn("cda", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.cda)
        self.assertIn("amda", spz.inventories.tree.__dict__)
        self.assertIsNotNone(spz.amda)
