"""Daily real-server probes for CDAWeb upstream-drift detection.

These tests run on the contract tier (daily cron) and hit the live
NASA CDAWeb service. Failures here mean CDA changed something we
depend on - the relevant cassettes need re-recording.

Most of CDA's coverage runs on the unit tier via cassettes. This file
keeps the cassette-tier in budget by hosting the few probes whose
recorded payloads would be too large to ship as cassettes:

- A full-inventory fetch (multi-hundred-MB response).
- A FEEPS electron-intensity request known to recover a large CDF.

It also adds two short smoke probes against well-known datasets so a
failure here actually says "CDA changed", not "this one large dataset
moved".
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone

import pytest

import speasy as spz
from speasy.products import SpeasyVariable

pytestmark = pytest.mark.contract


def _reset_cda_inventory_cache_flags() -> None:
    spz.core.index.index.set("cdaweb-inventory", "masters-last-modified", "")
    spz.core.index.index.set("cdaweb-inventory", "xml_catalog-last-modified", "")
    if spz.core.index.index.contains("cdaweb-inventory", "tree"):
        spz.core.index.index.pop("cdaweb-inventory", "tree")


class CdaWebContractProbes(unittest.TestCase):

    def test_short_request_returns_speasy_variable(self) -> None:
        result = spz.cda.get_variable(
            dataset="THA_L2_FGM",
            variable="tha_fgl_gsm",
            start_time=datetime(2014, 6, 1, tzinfo=timezone.utc),
            stop_time=datetime(2014, 6, 1, 0, 5, tzinfo=timezone.utc),
            disable_proxy=True,
            disable_cache=True,
            method="API",
        )
        self.assertIsInstance(result, SpeasyVariable)
        self.assertGreater(len(result), 0)

    def test_inventory_has_known_dataset(self) -> None:
        from speasy.inventories import flat_inventories
        # Loaded at import time; just probe a well-known node.
        self.assertIn("THA_L2_FGM", flat_inventories.cda.datasets)

    def test_full_inventory_fetch_finds_at_least_47000_parameters(self) -> None:
        # Full inventory pull is a multi-hundred-MB response - too large for
        # a cassette but cheap-enough to run daily as a drift probe.
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        _reset_cda_inventory_cache_flags()
        try:
            spz.cda.update_inventory()
            self.assertGreaterEqual(
                len(spz.inventories.flat_inventories.cda.parameters), 47000
            )
        finally:
            os.environ.pop(spz.config.proxy.enabled.env_var_name, None)

    def test_feeps_electron_intensity_returns_data(self) -> None:
        # MMS FEEPS payloads are large CDFs; not cassette-friendly.
        result = spz.get_data(
            "cda/MMS1_FEEPS_SRVY_L2_ELECTRON/"
            "mms1_epd_feeps_srvy_l2_electron_bottom_intensity_sensorid_2",
            datetime(2018, 5, 26, 1, 0, 0),
            datetime(2018, 5, 26, 1, 10, 1),
            disable_proxy=True,
            disable_cache=True,
        )
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
