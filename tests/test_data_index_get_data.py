import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import numpy as np

import speasy.data_index as data_index
from speasy.core import epoch_to_datetime64
from speasy.core.inventory.indexes import ParameterIndex
from speasy.data_index import DataIndex
from speasy.data_index._keys import data_key
from speasy.products import Catalog
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis

DAY = timedelta(days=1)


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _hourly(start, stop, value=1.):
    index = np.arange(start.timestamp(), stop.timestamp(), 3600.)
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
                          values=DataContainer(values=np.full(len(index), value)))


class _Server:
    """Stands for spz.get_data: records every request and serves hourly data, or what a test sets."""

    def __init__(self):
        self.calls = []
        self.answer = lambda start, stop: _hourly(start, stop, len(self.calls))

    def __call__(self, product, start, stop, **kwargs):
        self.calls.append((product, start, stop, kwargs))
        return self.answer(start, stop)


class _Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class GetDataTestCase(unittest.TestCase):
    NOW = _utc(2026, 10, 23, 12)

    def setUp(self):
        self.server = _Server()
        self.clock = _Clock(self.NOW)
        for name, value in (('_spz_get_data', self.server), ('_now', self.clock)):
            patcher = mock.patch.object(data_index, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.index = DataIndex(tempfile.mkdtemp())
        self.addCleanup(self.index.close)

    def get(self, start, stop, product='ssc/ace', **kwargs):
        return self.index.get_data(product, start, stop, **kwargs)


class Fetching(GetDataTestCase):
    def test_a_covered_request_makes_no_request(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 3))
        v = self.get(_utc(2023, 1, 1, 6), _utc(2023, 1, 2, 6))
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual((v.time[0], v.time[-1]), (np.datetime64('2023-01-01T06:00'), np.datetime64('2023-01-02T05:00')))

    def test_only_the_missing_runs_are_fetched(self):
        self.get(_utc(2023, 1, 2), _utc(2023, 1, 3))
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 5))
        self.assertEqual([(c[1], c[2]) for c in self.server.calls[1:]],
                         [(_utc(2023, 1, 1), _utc(2023, 1, 2)), (_utc(2023, 1, 3), _utc(2023, 1, 5))])

    def test_runs_never_ask_for_the_future(self):
        self.get(self.NOW - DAY, self.NOW + 30 * DAY)
        self.assertEqual(self.server.calls[0][1:3], (_utc(2026, 10, 22), self.NOW))

    def test_a_request_entirely_in_the_future_fetches_nothing(self):
        self.assertIsNone(self.get(self.NOW + DAY, self.NOW + 2 * DAY))
        self.assertEqual(self.server.calls, [])

    def test_an_inverted_range_raises(self):
        with self.assertRaisesRegex(ValueError, "stop.*after.*start"):
            self.get(_utc(2023, 1, 2), _utc(2023, 1, 1))

    def test_an_inventory_node_is_a_product_too(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), product=ParameterIndex('ace', 'ssc', 'ace'))
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), product='sscweb/ace')
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual(self.server.calls[0][0], 'ssc/ace')

    def test_only_time_series_are_stored(self):
        self.server.answer = lambda start, stop: Catalog(name='events')
        with self.assertRaisesRegex(TypeError, "time series"):
            self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))


class EmptyFragments(GetDataTestCase):
    def test_no_data_is_stored_and_not_fetched_again(self):
        self.server.answer = lambda start, stop: None
        self.assertIsNone(self.get(_utc(2023, 1, 1), _utc(2023, 1, 3)))
        self.assertIsNone(self.get(_utc(2023, 1, 1), _utc(2023, 1, 3)))
        self.assertEqual(len(self.server.calls), 1)

    def test_a_partly_empty_run_stores_rows_then_an_empty_fragment(self):
        self.server.answer = lambda start, stop: _hourly(start, start + DAY)
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 3))
        entries = [self.index.read_fragment('ssc/ace', {'coordinate_system': 'gse'}, day)
                   for day in (_utc(2023, 1, 1), _utc(2023, 1, 2))]
        self.assertEqual((len(entries[0].variable), entries[1].variable), (24, None))

    def test_a_zero_row_variable_is_stored_as_empty(self):
        self.server.answer = lambda start, stop: _hourly(start, start)
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))
        self.assertIsNone(self.index.read_fragment('ssc/ace', {'coordinate_system': 'gse'}, _utc(2023, 1, 1)).variable)


class Refresh(GetDataTestCase):
    def test_refresh_downloads_again_past_the_provider_cache(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))
        v = self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), refresh=True)
        self.assertTrue(self.server.calls[-1][3]['force_refresh'])
        self.assertTrue(np.all(v.values == 2.))

    def test_a_refresh_that_finds_nothing_empties_the_fragment(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))
        self.server.answer = lambda start, stop: None
        self.assertIsNone(self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), refresh=True))


class LiveEdge(GetDataTestCase):
    def setUp(self):
        super().setUp()
        self.get(self.NOW - DAY, self.NOW)   # today's fragment is stored half filled

    def test_is_refetched_once_an_hour_old(self):
        self.get(self.NOW - DAY, self.NOW)
        self.assertEqual(len(self.server.calls), 1)
        self.clock.now = self.NOW + timedelta(hours=1)
        self.get(self.NOW - DAY, self.NOW)
        self.assertEqual(self.server.calls[-1][1:3], (_utc(2026, 10, 23), self.NOW + timedelta(hours=1)))

    def test_is_final_once_refetched_after_its_end(self):
        self.clock.now = self.NOW + DAY
        self.get(self.NOW - DAY, self.NOW)
        self.clock.now = self.NOW + 3 * DAY
        self.get(self.NOW - DAY, self.NOW)
        self.assertEqual(len(self.server.calls), 2)

    def test_offline_keeps_the_stored_rows_and_warns_once(self):
        def offline(start, stop):
            raise ConnectionError("offline")
        self.server.answer = offline
        self.clock.now = self.NOW + timedelta(hours=2)
        with self.assertLogs('speasy.data_index', level='WARNING') as logs:
            v1 = self.get(self.NOW - DAY, self.NOW)
            v2 = self.get(self.NOW - DAY, self.NOW)
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(len(v1), len(v2))
        self.assertEqual(len(v1), 24)

    def test_an_automatic_refetch_finding_nothing_keeps_the_stored_rows(self):
        self.server.answer = lambda start, stop: None
        self.clock.now = self.NOW + timedelta(hours=2)
        self.assertEqual(len(self.get(self.NOW - DAY, self.NOW)), 24)


class PartialFailure(GetDataTestCase):
    def test_the_other_runs_are_stored_before_the_error(self):
        self.get(_utc(2023, 1, 2), _utc(2023, 1, 3))

        def fails_on_the_first_day(start, stop):
            if start == _utc(2023, 1, 1):
                raise ConnectionError("down")
            return _hourly(start, stop)
        self.server.answer = fails_on_the_first_day
        with self.assertRaises(ConnectionError):
            self.get(_utc(2023, 1, 1), _utc(2023, 1, 5))
        self.assertIsNotNone(self.index.read_fragment('ssc/ace', {'coordinate_system': 'gse'}, _utc(2023, 1, 4)))


class Kwargs(GetDataTestCase):
    def test_options_select_their_own_entries(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), coordinate_system='geo')
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), coordinate_system='GSE')
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))
        self.assertEqual(len(self.server.calls), 2)
        self.assertEqual(self.server.calls[0][3], {'coordinate_system': 'geo'})

    def test_a_misspelt_option_raises_even_on_a_covered_range(self):
        # it would otherwise serve the default frame's data, where a cold index raises
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))
        with self.assertRaisesRegex(TypeError, "coordinate_sytem"):
            self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), coordinate_sytem='geo')

    def test_transport_and_cache_options_are_accepted_and_not_keyed(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), disable_proxy=True, extra_http_headers={'a': 'b'})
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), prefer_cache=True)
        self.assertEqual(len(self.server.calls), 1)

    def test_numpy_values_in_options_are_fine(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), product='amda/some_template',
                 product_inputs={'threshold': np.float64(2.5)})
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), product='amda/some_template', product_inputs={'threshold': 2.5})
        self.assertEqual(len(self.server.calls), 1)


class UpdateAllData(GetDataTestCase):
    def test_downloads_every_stored_run_again_with_its_options(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 3), coordinate_system='geo')
        self.get(_utc(2023, 1, 10), _utc(2023, 1, 11), product='cda/AC_H0_MFI/BGSEc')
        self.server.calls.clear()
        self.index.update_all_data()
        self.assertEqual(sorted((c[0], c[1], c[2], c[3].get('coordinate_system')) for c in self.server.calls),
                         [('cda/AC_H0_MFI/BGSEc', _utc(2023, 1, 10), _utc(2023, 1, 11), None),
                          ('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 3), 'geo')])
        self.assertTrue(all(c[3]['force_refresh'] for c in self.server.calls))

    def test_only_the_given_products_any_alias(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), product='cda/AC_H0_MFI/BGSEc')
        self.server.calls.clear()
        self.index.update_all_data(['sscweb/ace'])
        self.assertEqual([c[0] for c in self.server.calls], ['ssc/ace'])


class Portability(unittest.TestCase):
    def test_keys_of_a_provider_that_isnt_installed_can_be_built(self):
        # an index from a colleague may hold a plugin provider's products
        self.assertEqual(data_key('someplugin', 'x', 'h', _utc(2023, 1, 1)), 'data/someplugin/x/h/2023-01-01T00:00:00Z')

    def test_two_index_instances_on_one_folder(self):
        path = tempfile.mkdtemp()
        with DataIndex(path) as a, DataIndex(path) as b:
            a.write_fragment('ssc/ace', {}, _utc(2023, 1, 1), _hourly(_utc(2023, 1, 1), _utc(2023, 1, 2)), fetched_at=1)
            b.write_fragment('ssc/ace', {}, _utc(2023, 1, 1), _hourly(_utc(2023, 1, 1), _utc(2023, 1, 2), 2.), fetched_at=2)
            self.assertEqual(a.read_fragment('ssc/ace', {}, _utc(2023, 1, 1)).fetched_at, 2)


if __name__ == '__main__':
    unittest.main()
