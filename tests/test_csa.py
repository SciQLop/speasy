import os
import unittest

import speasy as spz


class CSAInventory(unittest.TestCase):
    def test_can_get_full_inventory_without_proxy(self):
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        spz.csa.update_inventory()
        os.environ.pop(spz.config.proxy.enabled.env_var_name)
        self.assertGreaterEqual(len(spz.inventories.flat_inventories.csa.parameters), 1993)
        self.assertIn('flux__C1_CP_CIS_HIA_HS_1D_PEF',
                      spz.inventories.tree.csa.Cluster.Cluster_1.CIS_HIA1.C1_CP_CIS_HIA_HS_1D_PEF.__dict__)


if __name__ == '__main__':
    unittest.main()
