"""Fixes from the adversarial review of the data index: anything spz.get_data does, the index does too."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import numpy as np

import speasy.data_index as data_index
from speasy.core import dataprovider
from speasy.core.datetime_range import DateTimeRange
from speasy.core.inventory.indexes import ParameterIndex
from speasy.data_index import DataIndex
from speasy.data_index._storable import NotStorable, Serializer, from_storable, to_storable
from speasy.products import Catalog, Event, TimeTable
from tests.test_data_index_get_data import _Clock, _Server, _hourly, _utc

DAY = timedelta(days=1)
NOW = _utc(2026, 10, 23, 12)


class ParityTestCase(unittest.TestCase):
    def setUp(self):
        self.server = _Server()
        self.clock = _Clock(NOW)
        for name, value in (('_spz_get_data', self.server), ('_now', self.clock)):
            patcher = mock.patch.object(data_index, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.index = DataIndex(tempfile.mkdtemp())
        self.addCleanup(self.index.close)


class ProviderNotInstalled(ParityTestCase):
    """An index from a colleague may hold a plugin provider's products: reading them must not need the plugin."""

    def setUp(self):
        super().setUp()
        self.index.write_fragment('someplugin/x', {'frame': 'GSE'}, _utc(2023, 1, 1),
                                  _hourly(_utc(2023, 1, 1), _utc(2023, 1, 2)), fetched_at=int(NOW.timestamp()))

    def test_stored_data_is_served(self):
        self.assertEqual(len(self.index.get_data('someplugin/x', _utc(2023, 1, 1), _utc(2023, 1, 2))), 24)
        self.assertEqual(self.server.calls, [])

    def test_the_options_select_among_several_stored_ones(self):
        self.index.write_fragment('someplugin/x', {'frame': 'GSM'}, _utc(2023, 1, 1),
                                  _hourly(_utc(2023, 1, 1), _utc(2023, 1, 2), 2.), fetched_at=int(NOW.timestamp()))
        v = self.index.get_data('someplugin/x', _utc(2023, 1, 1), _utc(2023, 1, 2), frame='GSM')
        self.assertEqual(v.values[0, 0], 2.)
        start, stop = _utc(2023, 1, 1), _utc(2023, 1, 2)
        with self.assertRaisesRegex(ValueError, "several.*frame"):
            self.index.get_data('someplugin/x', start, stop)

    def test_what_isnt_stored_says_the_provider_is_missing(self):
        start, stop = _utc(2023, 1, 1), _utc(2023, 1, 3)
        with self.assertRaisesRegex(ValueError, "someplugin.*isn't installed"):
            self.index.get_data('someplugin/x', start, stop)


class CacheOptionsKeepTheirMeaning(ParityTestCase):
    def setUp(self):
        super().setUp()
        self.index.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2))

    def test_force_refresh_downloads_again_a_covered_range(self):
        self.index.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2), force_refresh=True)
        self.assertEqual(len(self.server.calls), 2)

    def test_disable_cache_downloads_again_a_covered_range(self):
        self.index.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2), disable_cache=True)
        self.assertEqual(len(self.server.calls), 2)


class _Plugin(dataprovider.DataProvider):
    """A third-party provider that takes its own options but declares no request_options."""
    NAME = 'parityplugin'

    def get_data(self, product, start_time, stop_time, coordinate_frame='GSE', **kwargs):
        raise AssertionError("never started in these tests")


class ProviderWithoutRequestOptions(ParityTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(dataprovider._PROVIDER_CLASSES, {'parityplugin': _Plugin})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_its_options_are_accepted_and_keep_their_data_apart(self):
        # with nothing in the key, a GSM request would have been served the stored GSE data
        self.index.get_data('parityplugin/x', _utc(2023, 1, 1), _utc(2023, 1, 2), coordinate_frame='GSE')
        self.index.get_data('parityplugin/x', _utc(2023, 1, 1), _utc(2023, 1, 2), coordinate_frame='GSM')
        self.assertEqual(len(self.server.calls), 2)

    def test_cache_and_transport_options_stay_out_of_the_key(self):
        self.index.get_data('parityplugin/x', _utc(2023, 1, 1), _utc(2023, 1, 2))
        self.index.get_data('parityplugin/x', _utc(2023, 1, 1), _utc(2023, 1, 2), extra_http_headers={'a': 'b'})
        self.assertEqual(len(self.server.calls), 1)


class _BareProvider:
    """A provider that isn't a DataProvider at all, like the virtual products one: get_data is all it has."""
    NAME = 'bareprovider'

    def get_data(self, product, start_time, stop_time, **kwargs):
        raise AssertionError("never started in these tests")


class ProviderNotADataProvider(ParityTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(dataprovider._PROVIDER_CLASSES, {'bareprovider': _BareProvider})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_its_data_is_stored_and_served(self):
        self.index.get_data('bareprovider/x', _utc(2023, 1, 1), _utc(2023, 1, 2))
        self.index.get_data('bareprovider/x', _utc(2023, 1, 1), _utc(2023, 1, 2))
        self.assertEqual(len(self.server.calls), 1)


class TimetableWithARange(ParityTestCase):
    def setUp(self):
        super().setUp()
        self.server.answer = lambda start, stop: TimeTable('storms', dt_ranges=[DateTimeRange(_utc(2023, 1, 1),
                                                                                             _utc(2023, 1, 2))])

    def test_is_fetched_once_and_replays_offline(self):
        first = self.index.get_data('amda/storms', _utc(2023, 1, 1), _utc(2023, 2, 1))
        again = self.index.get_data('amda/storms', _utc(2023, 1, 1), _utc(2023, 2, 1))
        whole = self.index.get_data('amda/storms')
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual(list(again), list(first))
        self.assertEqual(list(whole), list(first))


class MetaIsKeptAsItWas(unittest.TestCase):
    def round_trip(self, value):
        return from_storable(Serializer().loads(Serializer().dumps(to_storable(value))))

    def test_types_survive(self):
        meta = {'naive': datetime(2020, 1, 1), 'aware': _utc(2020, 1, 1), 'np': np.datetime64('2020-01-01T00:00:00.5'),
                'pair': (1, 2), 'z': 1 + 2j, 'labels': np.array(['a', 'bc'], dtype=object)}
        restored = self.round_trip(meta)
        for key in ('naive', 'aware', 'np', 'pair', 'z'):
            with self.subTest(key=key):
                self.assertEqual(restored[key], meta[key])
                self.assertIs(type(restored[key]), type(meta[key]))
        np.testing.assert_array_equal(restored['labels'], meta['labels'])

    def test_inventory_nodes_in_meta_survive(self):
        # AMDA puts inventory nodes in its catalogs' meta
        node = ParameterIndex('imf', 'amda', 'imf', meta={'units': 'nT'})
        restored = self.round_trip({'parameter': node})['parameter']
        self.assertIsInstance(restored, ParameterIndex)
        self.assertEqual(restored.spz_uid(), 'imf')
        self.assertEqual(restored.units, 'nT')

    def test_what_still_cant_be_stored_names_its_field(self):
        with self.assertRaisesRegex(NotStorable, "meta/thing.*object"):
            to_storable({'meta': {'thing': object()}})

    def test_a_catalog_with_inventory_nodes_in_its_meta_is_stored(self):
        index = DataIndex(tempfile.mkdtemp())
        self.addCleanup(index.close)
        node = ParameterIndex('imf', 'amda', 'imf')
        server = _Server()
        server.static_answer = lambda: Catalog('events', meta={'parameter': node}, events=[Event(_utc(2023, 1, 1),
                                                                                                 _utc(2023, 1, 2))])
        with mock.patch.object(data_index, '_spz_get_data', server):
            index.get_data('amda/events')
            catalog = index.get_data('amda/events')
        self.assertEqual(len(server.calls), 1)
        self.assertEqual(catalog.meta['parameter'].spz_uid(), 'imf')


class ImportRobustness(ParityTestCase):
    def test_a_malformed_local_entry_is_replaced(self):
        source = DataIndex(tempfile.mkdtemp())
        source.write_fragment('ssc/ace', {}, _utc(2023, 1, 1), _hourly(_utc(2023, 1, 1), _utc(2023, 1, 2)), fetched_at=5)
        source.close()
        from speasy.data_index._keys import data_key
        self.index._store[data_key('ssc', 'ace', data_index.options_hash({}), _utc(2023, 1, 1))] = {'broken': True}
        self.index.import_data(source.path)
        self.assertEqual(self.index.read_fragment('ssc/ace', {}, _utc(2023, 1, 1)).fetched_at, 5)


class Reuse(ParityTestCase):
    def test_an_index_is_still_usable_after_its_with_block(self):
        # a notebook enters `with index:` in several cells
        with self.index:
            pass
        with self.index:
            self.assertEqual(len(self.index.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2))), 24)
        self.assertEqual(len(self.index.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2))), 24)


class Cli(unittest.TestCase):
    def test_info_and_export_dont_create_an_index_at_a_mistyped_path(self):
        from tests.test_cli import _run
        missing = os.path.join(tempfile.mkdtemp(), 'typo')
        for argv in (('index', 'info', missing), ('index', 'export', missing, missing + '.tar')):
            with self.subTest(command=argv[1]):
                code, out = _run(*argv)
                self.assertEqual(code, 1)
                self.assertIn('no data index at', out)
                self.assertFalse(os.path.exists(missing))


if __name__ == '__main__':
    unittest.main()
