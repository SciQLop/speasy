#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the diskcache -> sciqlop-cache migration."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import diskcache
import pysciqlop_cache as sc

from speasy.core.cache.cache import _migrate_legacy_diskcache


class LegacyDiskcacheMigration(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="spz_mig_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        # _migrate_legacy_diskcache leaves a <path>.diskcache.backup sibling
        self.addCleanup(shutil.rmtree, f"{self.root}.diskcache.backup", ignore_errors=True)
        self.addCleanup(shutil.rmtree, f"{self.root}.sciqlop_migrating", ignore_errors=True)

    def test_large_value_survives_migration(self):
        """Large values are stored by sciqlop-cache as external files referenced
        by absolute path. ``_migrate_legacy_diskcache`` migrates into a staging
        directory then renames it to the final path -- which orphans every
        external (large) value while inline (small) values survive. This is the
        desync that drops ``proxy_inventories/<provider>`` to ``None`` while the
        ``proxy_inventories_save_date`` datetime stays, crashing provider init.
        """
        legacy = diskcache.Cache(self.root)
        big = {"payload": "x" * 200_000}      # large -> externalized to a file
        legacy["proxy_inventories/amda"] = big
        legacy["proxy_inventories_save_date/amda"] = "2024-01-01T00:00:00+00:00"
        legacy.close()

        self.assertTrue(_migrate_legacy_diskcache(self.root))

        migrated = sc.Index(path=self.root)
        self.assertEqual(
            migrated.get("proxy_inventories/amda", None), big,
            "large value was orphaned by the migration's directory rename")
        self.assertEqual(
            migrated.get("proxy_inventories_save_date/amda", None),
            "2024-01-01T00:00:00+00:00")

    def test_falls_back_gracefully_when_diskcache_unavailable(self):
        """diskcache is a dev-only dependency now (not installed for regular
        users). ``migrate()`` imports it lazily inside its own body, so a
        legacy cache detected on a machine without diskcache installed must
        not crash the caller -- it should log and leave the legacy cache
        untouched so Speasy falls back to a fresh cache at the same path.
        """
        legacy = diskcache.Cache(self.root)
        legacy["some_key"] = "some_value"
        legacy.close()

        with mock.patch.dict(sys.modules, {"diskcache": None}):
            migrated = _migrate_legacy_diskcache(self.root)

        self.assertFalse(migrated)
        self.assertTrue(
            os.path.isfile(os.path.join(self.root, "cache.db")),
            "legacy cache should be left untouched when migration can't run")


if __name__ == "__main__":
    unittest.main()
