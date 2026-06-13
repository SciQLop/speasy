"""Daily real-server probes for AMDA upstream-drift detection.

These tests run on the contract tier (daily cron) and hit the live
AMDA service. Failures here mean AMDA changed something we depend on
— the relevant cassettes in tests/cassettes/test_amda*/ need
re-recording.

Keep this file small: 3-5 probes covering the critical capabilities.
The bulk of AMDA test coverage runs on the unit tier via cassettes.
"""

from __future__ import annotations

import unittest
from datetime import datetime

import pytest

import speasy as spz
from speasy.products import SpeasyVariable

pytestmark = pytest.mark.contract


class AmdaContractProbes(unittest.TestCase):

    def setUp(self) -> None:
        self.start = datetime(2018, 1, 1)
        self.stop = datetime(2018, 1, 1, 0, 5)

    def test_get_parameter_returns_speasy_variable(self) -> None:
        result = spz.amda.get_parameter(
            "imf", self.start, self.stop, disable_proxy=True, disable_cache=True
        )
        self.assertIsInstance(result, SpeasyVariable)
        self.assertGreater(len(result), 0)

    def test_get_dataset_returns_dataset(self) -> None:
        result = spz.amda.get_dataset(
            "ace-imf-all", self.start, self.stop, disable_proxy=True, disable_cache=True
        )
        self.assertIsNotNone(result)

    def test_inventory_loads(self) -> None:
        # Inventory is loaded at import time; just probe one well-known node.
        from speasy.inventories import flat_inventories
        self.assertGreater(len(flat_inventories.amda.parameters), 100)

    def test_list_catalogs_returns_a_list(self) -> None:
        catalogs = spz.amda.list_catalogs()
        self.assertIsInstance(catalogs, list)
        self.assertGreater(len(catalogs), 0)

    def test_list_timetables_returns_a_list(self) -> None:
        timetables = spz.amda.list_timetables()
        self.assertIsInstance(timetables, list)
        self.assertGreater(len(timetables), 0)
