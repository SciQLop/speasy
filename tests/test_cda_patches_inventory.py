import unittest
from collections import Counter
from datetime import datetime, timezone
from unittest import mock

from speasy.core import dataprovider as dp
from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import DatasetIndex, ParameterIndex, SpeasyIndex, make_inventory_node, to_dict
from speasy.data_providers.cda._patches import table
from speasy.data_providers.cda._patches.inventory import patch_inventory
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


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
SIBLING = InjectedDataset('NEW_DS', 'OLD_DS', 'new_%Y%m%d_v01.cdf', 'https://x/new', 'yearly', 'new_00000000_v01.cdf',
                          '2020-04-15T00:00:00Z', 'an injected dataset')
VIRTUAL_F = PatchedParameter('OLD_DS', 'wave_f', 'wave', TimeMatrix('time'))
NEW_F0 = PatchedParameter('NEW_DS', 'wave_F0', 'wave', TimeMatrix('time'), meta={'spz_shape': 3, 'UNITS': 'V'})


def _tree():
    root = SpeasyIndex('cda', 'cda', 'cda')
    mission = make_inventory_node(root, SpeasyIndex, 'Mission', 'cda', 'Mission')
    dataset = make_inventory_node(mission, DatasetIndex, 'OLD_DS', 'cda', 'OLD_DS',
                                  start_date='2018-01-01T00:00:00Z', stop_date='2025-01-01T00:00:00Z')
    make_inventory_node(dataset, ParameterIndex, 'wave_f', 'cda', 'OLD_DS/wave_f', VIRTUAL='TRUE',
                        spz_shape=(2048,), dataset='OLD_DS')
    return root


def _patched(patches=(VIRTUAL_F, NEW_F0), injected=(SIBLING,), root=None):
    with mock.patch.object(table, 'PATCHES', patches), mock.patch.object(table, 'INJECTED', injected):
        return patch_inventory(root or _tree(), NOW)


class InventoryPatch(unittest.TestCase):
    def test_injects_dataset_next_to_sibling(self):
        injected = _patched().Mission.NEW_DS
        self.assertIsInstance(injected, DatasetIndex)
        self.assertEqual((injected.spz_uid(), injected.spz_provider()), ('NEW_DS', 'cda'))
        self.assertEqual((injected.filenaming, injected.url, injected.subdividedby, injected.mastercdf),
                         ('new_%Y%m%d_v01.cdf', 'https://x/new', 'yearly', 'new_00000000_v01.cdf'))
        self.assertEqual((injected.start_date, injected.description), ('2020-04-15T00:00:00Z', 'an injected dataset'))

    def test_injected_stop_date_is_now(self):
        self.assertEqual(_patched().Mission.NEW_DS.stop_date, NOW.isoformat())

    def test_already_injected_dataset_gets_this_load_stop_date(self):
        root = _patched()
        root.Mission.NEW_DS.stop_date = '2026-01-01T00:00:00+00:00'
        self.assertEqual(_patched(root=root).Mission.NEW_DS.stop_date, NOW.isoformat())

    def test_unvirtualizes_patched_param(self):
        param = _patched().Mission.OLD_DS.wave_f
        self.assertNotIn('VIRTUAL', param.__dict__)
        self.assertEqual((param.spz_shape, param.dataset), (1, 'OLD_DS'))
        self.assertEqual((param.start_date, param.stop_date), ('2018-01-01T00:00:00Z', '2025-01-01T00:00:00Z'))

    def test_creates_new_param(self):
        param = _patched().Mission.NEW_DS.wave_F0
        self.assertIsInstance(param, ParameterIndex)
        self.assertEqual((param.spz_uid(), param.spz_name()), ('NEW_DS/wave_F0', 'wave_F0'))
        self.assertEqual((param.spz_shape, param.UNITS, param.dataset), (3, 'V', 'NEW_DS'))
        self.assertEqual((param.start_date, param.stop_date), ('2020-04-15T00:00:00Z', NOW.isoformat()))

    def test_idempotent(self):
        once = _patched()
        self.assertEqual(to_dict(_patched(root=once), version=2), to_dict(_patched(), version=2))

    def test_missing_sibling_is_skipped_with_warning(self):
        orphan = InjectedDataset('ORPHAN', 'NO_SUCH_DS', 'f', 'u', 'None', 'm', '2020-01-01T00:00:00Z', 'd')
        with self.assertLogs('speasy.data_providers.cda._patches.inventory', level='WARNING') as logs:
            root = _patched(patches=(), injected=(orphan,))
        self.assertIn('NO_SUCH_DS', logs.output[0])
        self.assertEqual(to_dict(root, version=2), to_dict(_tree(), version=2))

    def test_entries_of_absent_datasets_are_skipped(self):
        orphan = PatchedParameter('NO_SUCH_DS', 'wave', 'wave', TimeMatrix('time'))
        self.assertEqual(to_dict(_patched(patches=(orphan,), injected=()), version=2), to_dict(_tree(), version=2))


class _Marking(DataProvider):
    NAME = 'patchhook'

    def __init__(self):
        DataProvider.__init__(self, inventory_disable_proxy=True)

    def build_inventory(self, root):
        return root

    def patch_inventory(self, root):
        make_inventory_node(root, DatasetIndex, 'MARK', 'patchhook', 'MARK')
        return root


class PatchInventoryHook(unittest.TestCase):
    def setUp(self):
        for patcher in (mock.patch.dict(dp.PROVIDERS), mock.patch.dict(dp.flat_inventories.__dict__),
                        mock.patch.dict(dp.tree.__dict__)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_update_inventory_calls_hook(self):
        self.assertIn('MARK', _Marking().flat_inventory.datasets)

    def test_default_hook_returns_root_unchanged(self):
        root = _tree()
        self.assertIs(DataProvider.patch_inventory(None, root), root)
