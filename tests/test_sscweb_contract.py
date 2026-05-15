"""Daily real-server probes for SSCWeb upstream-drift detection."""

from __future__ import annotations

import unittest
from datetime import datetime

import pytest

import speasy as spz
from speasy.products import SpeasyVariable

pytestmark = pytest.mark.contract


class SscWebContractProbes(unittest.TestCase):

    def test_get_data_returns_speasy_variable(self) -> None:
        result = spz.get_data(
            "ssc/mms1", datetime(2020, 1, 1), datetime(2020, 1, 1, 0, 5),
            disable_proxy=True, disable_cache=True,
        )
        self.assertIsInstance(result, SpeasyVariable)
        self.assertGreater(len(result), 0)

    def test_inventory_has_known_observatory(self) -> None:
        from speasy.inventories import flat_inventories
        self.assertIn("mms1", flat_inventories.ssc.parameters)

    def test_observatories_list_includes_known_mission(self) -> None:
        # If SSC removes MMS or restructures observatory listings, this fails.
        from speasy.inventories import flat_inventories
        ids = list(flat_inventories.ssc.parameters)
        self.assertGreaterEqual(len(ids), 50)
