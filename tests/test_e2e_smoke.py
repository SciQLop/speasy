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
        # Try a handful of GenericArchive products until one returns data. The
        # smoke goal is to confirm the GenericArchive code path runs end-to-end;
        # we don't care which product yields data, just that some product does.
        # We sample across the full inventory rather than the first N entries
        # since the order can group products by mission, and a given time range
        # may not match every mission's operational period.
        from speasy.inventories import flat_inventories
        params = flat_inventories.generic_archive.parameters
        if not params:
            self.skipTest("no GenericArchive products configured")
        items = list(params.items())
        step = max(1, len(items) // 30)
        candidates = items[::step][:30]
        last_error: Exception | None = None
        for _, product in candidates:
            try:
                result = spz.get_data(product, START, STOP)
            except Exception as e:
                last_error = e
                continue
            if isinstance(result, SpeasyVariable) and len(result) > 0:
                return
        if last_error is not None:
            self.fail(
                f"all {len(candidates)} GenericArchive candidates raised; "
                f"last error: {last_error!r}"
            )
        self.skipTest("no GenericArchive product yielded data for the smoke time range")
