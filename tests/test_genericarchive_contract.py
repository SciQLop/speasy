"""Daily real-server probes for GenericArchive upstream-drift detection.

These tests run on the contract tier (daily cron) and hit the live
LPP and CDA mirror endpoints. Failures here mean an upstream changed
something we depend on — the relevant cassettes in
tests/cassettes/test_direct_archive_downloader/ or test_file_access/
need re-recording, or a code-side adjustment.

Keep small (4-5 probes); the bulk of GenericArchive coverage runs on
the unit tier via cassettes.
"""

from __future__ import annotations

import unittest

import pytest

import speasy as spz
from speasy.core.any_files import any_loc_open
from speasy.products import SpeasyVariable

pytestmark = pytest.mark.contract


class GenericArchiveContractProbes(unittest.TestCase):

    def test_can_open_remote_http_text_resource(self) -> None:
        """LPP cache server still serves HTML at /cache/."""
        f = any_loc_open(
            "http://sciqlop.lpp.polytechnique.fr/cache/", mode="r"
        )
        content = f.read()
        self.assertIn("<", content)

    def test_can_open_remote_http_binary_resource(self) -> None:
        """LPP data server still serves binary files at /data/."""
        f = any_loc_open(
            "https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw",
            mode="rb",
        )
        content = f.read(4)
        self.assertGreater(len(content), 0)

    def test_mms_fpi_burst_returns_data(self) -> None:
        """MMS FPI burst products still resolve via the CDA mirror.
        Skipped from the unit tier because cassettes are ~370-650 MB."""
        result = spz.get_data(
            "archive/cda/MMS/MMS1/FPI/BURST/MOMS/mms1_fpi_brst_l2_des_moms/mms1_des_energyspectr_mz_brst",
            "2018-01-30T10",
            "2018-01-30T11",  # 1 hour to limit transfer
            disable_cache=True,
        )
        self.assertIsInstance(result, SpeasyVariable)

    def test_remote_text_resource_assertion_still_holds(self) -> None:
        """The Vbias HTML resource still returns a parseable HTML document.
        Skipped from the unit tier because the response body is ~137 MB."""
        f = any_loc_open(
            "https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html",
            mode="r",
        )
        head = f.read(1024)
        self.assertIn("<!DOCTYPE", head.upper())
