"""Daily real-server probes for CSA upstream-drift detection."""

from __future__ import annotations

import os
import unittest

import pytest

import speasy as spz

pytestmark = pytest.mark.contract


class CsaContractProbes(unittest.TestCase):

    def test_inventory_fetch_returns_at_least_1932_parameters(self) -> None:
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        try:
            spz.csa.update_inventory()
            self.assertGreaterEqual(
                len(spz.inventories.flat_inventories.csa.parameters), 1932
            )
        finally:
            os.environ.pop(spz.config.proxy.enabled.env_var_name, None)

    def test_inventory_contains_known_cluster_parameter(self) -> None:
        # If CSA renames or restructures Cluster CIS HIA products, this probe fails.
        cis = spz.inventories.tree.csa.Cluster.Cluster_1.CIS_HIA1
        self.assertTrue(hasattr(cis, "C1_CP_CIS_HIA_HS_1D_PEF"))
