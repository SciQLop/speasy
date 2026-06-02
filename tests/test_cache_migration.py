#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the diskcache -> sciqlop-cache migration."""
import os
import shutil
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
