#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the diskcache -> sciqlop-cache migration."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import diskcache
import pysciqlop_cache as sc

from speasy.core.cache.cache import (
    _migrate_legacy_diskcache,
    _is_legacy_diskcache_layout,
    _warn_if_backup_present,
    migration_backups,
    delete_migration_backups,
)


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
        """diskcache is a required runtime dependency, but ``migrate()`` imports it lazily
        inside its own body, so an unusual install (e.g. ``--no-deps``) missing it must not
        crash the caller when a legacy cache is detected -- it should log and leave the
        legacy cache untouched so Speasy falls back to a fresh cache at the same path.
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

    def test_stray_legacy_file_does_not_trigger_false_positive(self):
        """Real-world caches that migrated with an older pysciqlop-cache release can
        end up with a stray ``cache.db`` (diskcache's own filename) sitting next to
        the current backend's ``sciqlop-cache.db``, left over from before the file
        was renamed upstream. ``_is_legacy_diskcache_layout`` must not treat that
        leftover as a legacy layout needing (re-)migration -- presence of
        ``sciqlop-cache.db`` proves this directory is already on the new backend.
        Getting this wrong is dangerous: if a user later deletes the
        ``.diskcache.backup`` (as documented, once they've verified the cache
        works), the next import would see no backup and attempt to re-migrate a
        cache that never needed it, renaming the live cache away and feeding it to
        ``diskcache.Cache()``.
        """
        cache = sc.Cache(cache_path=self.root, max_size=int(20e9))
        cache.set("some_key", "some_value")
        del cache

        # Simulate the leftover from an older pysciqlop-cache release.
        with open(os.path.join(self.root, "cache.db"), "wb") as f:
            f.write(b"not a real diskcache database")

        self.assertFalse(_is_legacy_diskcache_layout(Path(self.root)))
        self.assertFalse(_migrate_legacy_diskcache(self.root))
        self.assertTrue(
            os.path.isfile(os.path.join(self.root, "sciqlop-cache.db")),
            "the live cache must be left untouched")

    def test_migration_backups_lists_and_deletes(self):
        """migration_backups()/delete_migration_backups() must find and remove
        the backup(s) _migrate_legacy_diskcache creates, without touching the
        live migrated cache.
        """
        legacy = diskcache.Cache(self.root)
        legacy["some_key"] = "some_value"
        legacy.close()
        self.assertTrue(_migrate_legacy_diskcache(self.root))

        backup = f"{self.root}.diskcache.backup"
        with mock.patch("speasy.core.cache.cache._known_migratable_paths", return_value=[self.root]):
            self.assertEqual(migration_backups(), [backup])
            deleted = delete_migration_backups()

        self.assertEqual(deleted, [backup])
        self.assertFalse(os.path.exists(backup))
        self.assertTrue(
            os.path.isfile(os.path.join(self.root, "sciqlop-cache.db")),
            "the live cache must be left untouched")

    def test_migration_backups_empty_when_none_exist(self):
        with mock.patch("speasy.core.cache.cache._known_migratable_paths", return_value=[self.root]):
            self.assertEqual(migration_backups(), [])
            self.assertEqual(delete_migration_backups(), [])

    def test_warn_if_backup_present_reminds_until_deleted(self):
        """The reminder must fire every time a backup is still around, and stop
        once it's gone -- this is what nags the user on each import."""
        legacy = diskcache.Cache(self.root)
        legacy["some_key"] = "some_value"
        legacy.close()
        self.assertTrue(_migrate_legacy_diskcache(self.root))

        with self.assertLogs("speasy.core.cache.cache", level="WARNING") as ctx:
            _warn_if_backup_present(self.root)
        self.assertIn("delete_migration_backups", ctx.output[0])

        shutil.rmtree(f"{self.root}.diskcache.backup")
        with self.assertNoLogs("speasy.core.cache.cache", level="WARNING"):
            _warn_if_backup_present(self.root)


if __name__ == "__main__":
    unittest.main()
