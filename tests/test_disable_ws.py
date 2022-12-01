import unittest

import os
import sys


def _drop_all_speazy_mods():
    keys = list(sys.modules.keys())
    for name in keys:
        if 'speasy' in name:
            sys.modules.pop(name)


class DisableWS(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_disable_amda(self):
        os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = "amda"
        _drop_all_speazy_mods()
        import speasy as spz
        self.assertNotIn("amda", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.amda)
        self.assertIn("cda", spz.inventories.tree.__dict__)
        self.assertIsNotNone(spz.cda)

    def test_disable_ssc_and_cda(self):
        os.environ["SPEASY_CORE_DISABLED_PROVIDERS"] = "ssc,cda"
        _drop_all_speazy_mods()
        import speasy as spz
        self.assertNotIn("ssc", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.ssc)
        self.assertNotIn("cda", spz.inventories.tree.__dict__)
        self.assertIsNone(spz.cda)
        self.assertIn("amda", spz.inventories.tree.__dict__)
        self.assertIsNotNone(spz.amda)
