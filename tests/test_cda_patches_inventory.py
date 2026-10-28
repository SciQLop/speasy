import unittest
from collections import Counter
from unittest import mock

from speasy.data_providers.cda._patches import table
from speasy.data_providers.cda._patches.decoders import TimeMatrix
from speasy.data_providers.cda._patches.table import InjectedDataset, PatchedParameter


class PatchTableSchema(unittest.TestCase):
    def test_patch_for_unknown_returns_none(self):
        self.assertIsNone(table.patch_for('NO_SUCH_DATASET', 'nope'))

    def test_patch_for_finds_entry(self):
        entry = PatchedParameter('DS', 'wave', 'wave_var', TimeMatrix('t'))
        with mock.patch.object(table, 'PATCHES', (entry,)):
            self.assertIs(table.patch_for('DS', 'wave'), entry)
            self.assertIsNone(table.patch_for('DS', 'other'))

    def test_is_injected(self):
        entry = InjectedDataset('NEW', 'OLD', 'f_$Y.cdf', 'http://x', 'monthly', 'm.cdf', '2020-01-01', 'd')
        with mock.patch.object(table, 'INJECTED', (entry,)):
            self.assertTrue(table.is_injected('NEW'))
            self.assertFalse(table.is_injected('OLD'))

    def test_table_has_no_duplicates(self):
        keys = Counter((p.dataset, p.name) for p in table.PATCHES)
        self.assertEqual([k for k, n in keys.items() if n > 1], [])
        ids = Counter(d.id for d in table.INJECTED)
        self.assertEqual([k for k, n in ids.items() if n > 1], [])
