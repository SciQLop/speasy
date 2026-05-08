"""End-to-end smoke tests.

These tests exercise the canonical user workflow (`spz.get_data` end-to-end)
once per active provider. They run on the full OS × Python matrix on a
weekly cron, confirming that Speasy installs and works on every supported
combination.

Goals:
- catch packaging/install regressions (something present in the dev env but
  missing from the published wheel);
- catch platform-specific issues (Windows tempfile handling, macOS arm64
  numpy ABI, etc.);
- catch new-Python-version regressions before users hit them.

Keep this file small: 1 test per provider, fast products, short time
ranges. If a test starts failing intermittently, move it to the contract
tier instead of expanding this file.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import pytest

import speasy as spz
from speasy.products import SpeasyVariable

pytestmark = pytest.mark.e2e

START = datetime(2018, 1, 1, tzinfo=timezone.utc)
STOP = datetime(2018, 1, 1, 0, 30, tzinfo=timezone.utc)


class E2ESmoke(unittest.TestCase):

    def test_amda(self):
        result = spz.get_data("amda/imf", START, STOP)
        self.assertIsInstance(result, SpeasyVariable)
        self.assertGreater(len(result), 0)

    def test_cda(self):
        result = spz.get_data(
            "cda/MMS1_FGM_SRVY_L2/mms1_fgm_b_gse_srvy_l2", START, STOP
        )
        self.assertIsInstance(result, SpeasyVariable)
        self.assertGreater(len(result), 0)

    def test_csa(self):
        result = spz.get_data("csa/C1_CP_FGM_SPIN/B_vec_xyz_gse__C1_CP_FGM_SPIN", START, STOP)
        self.assertIsInstance(result, SpeasyVariable)
        self.assertGreater(len(result), 0)

    def test_ssc(self):
        result = spz.get_data("ssc/mms1", START, STOP)
        self.assertIsInstance(result, SpeasyVariable)
        self.assertGreater(len(result), 0)

    def test_generic_archive(self):
        # Any reliable GenericArchive product. If this proves flaky, swap to a
        # known-stable archive entry from the inventory.
        from speasy.inventories.flat_inventories import generic_archive
        if not generic_archive.parameters:
            self.skipTest("no GenericArchive products configured")
        product_id = next(iter(generic_archive.parameters))
        result = spz.get_data(product_id, START, STOP)
        self.assertIsInstance(result, SpeasyVariable)
