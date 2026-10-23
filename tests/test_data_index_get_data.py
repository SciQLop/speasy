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
from speasy.core.datetime_range import DateTimeRange
from speasy.products import Catalog, Dataset, Event, TimeTable
from speasy.products.variable import DataContainer, SpeasyVariable, VariableTimeAxis

DAY = timedelta(days=1)


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _hourly(start, stop, value=1.):
    index = np.arange(start.timestamp(), stop.timestamp(), 3600.)
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
                          values=DataContainer(values=np.full(len(index), value)))


class _Server:
    """Stands for the provider: records every request and serves hourly data, a timetable for requests without a
    time range, or what a test sets."""

    def __init__(self):
        self.calls = []
        self.answer = lambda start, stop: _hourly(start, stop, len(self.calls))
        self.static_answer = lambda: TimeTable('storms', dt_ranges=[DateTimeRange(_utc(2023, 1, 1), _utc(2023, 1, 2))])

    def __call__(self, product, *time_range, **kwargs):
        if not time_range:
            self.calls.append((product, None, None, kwargs))
            return self.static_answer()
        self.calls.append((product, *time_range, kwargs))
        return self.answer(*time_range)


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
        start, stop = _utc(2023, 1, 2), _utc(2023, 1, 1)
        with self.assertRaisesRegex(ValueError, "stop.*after.*start"):
            self.get(start, stop)

    def test_an_inventory_node_is_a_product_too(self):
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), product=ParameterIndex('ace', 'ssc', 'ace'))
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2), product='sscweb/ace')
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual(self.server.calls[0][0], 'ssc/ace')

    def test_a_product_kind_the_index_doesnt_know_is_returned_unstored(self):
        # whatever spz.get_data gives, the index gives too
        self.server.answer = lambda start, stop: "some future product kind"
        self.assertEqual(self.get(_utc(2023, 1, 1), _utc(2023, 1, 2)), "some future product kind")
        self.assertEqual(self.index.requests(), [])


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
        self.assertEqual((len(entries[0].product), entries[1].product), (24, None))

    def test_a_zero_row_variable_is_stored_as_empty(self):
        self.server.answer = lambda start, stop: _hourly(start, start)
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 2))
        self.assertIsNone(self.index.read_fragment('ssc/ace', {'coordinate_system': 'gse'}, _utc(2023, 1, 1)).product)


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
        start, stop = _utc(2023, 1, 1), _utc(2023, 1, 5)
        with self.assertRaises(ConnectionError):
            self.get(start, stop)
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
        start, stop = _utc(2023, 1, 1), _utc(2023, 1, 2)
        with self.assertRaisesRegex(TypeError, "coordinate_sytem"):
            self.get(start, stop, coordinate_sytem='geo')

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


class Transparent(GetDataTestCase):
    """Inside `with DataIndex(...)`, spz.get_data goes through the index; outside, it is back to normal."""

    def setUp(self):
        super().setUp()
        import speasy.core.requests_scheduling.request_dispatch as dispatch
        patcher = mock.patch.object(dispatch, '_scalar_get_data', return_value='direct')
        self.direct = patcher.start()
        self.addCleanup(patcher.stop)

    def test_spz_get_data_goes_through_the_index_inside_the_block(self):
        import speasy as spz
        with self.index:
            spz.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2))
            v = spz.get_data('ssc/ace', (_utc(2023, 1, 1), _utc(2023, 1, 2)))   # a time range tuple too
        self.assertEqual((len(self.server.calls), len(v)), (1, 24))
        self.direct.assert_not_called()
        self.index = DataIndex(self.index.path)   # setUp's cleanup closes it

    def test_spz_get_data_is_back_to_normal_after_the_block(self):
        import speasy as spz
        with self.index:
            pass
        self.assertEqual(spz.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2)), 'direct')
        self.index = DataIndex(self.index.path)

    def test_back_to_normal_even_when_the_block_raises(self):
        import speasy as spz
        with self.assertRaises(RuntimeError), self.index:
            raise RuntimeError("boom")
        self.assertEqual(spz.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2)), 'direct')
        self.index = DataIndex(self.index.path)

    def test_nested_blocks_restore_the_outer_index(self):
        import speasy as spz
        outer, inner = DataIndex(tempfile.mkdtemp()), DataIndex(tempfile.mkdtemp())
        with outer:
            with inner:
                spz.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2))
            spz.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2))
        self.assertEqual(len(self.server.calls), 2)   # once into each index
        self.assertEqual(spz.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2)), 'direct')

    def test_timetables_and_catalogs_go_through_the_index_too(self):
        import speasy as spz
        with self.index:
            spz.get_data('amda/my_timetable')
            self.assertEqual(len(spz.get_data('amda/my_timetable')), 1)
        self.assertEqual(len(self.server.calls), 1)
        self.direct.assert_not_called()
        self.index = DataIndex(self.index.path)

    def test_datasets_go_through_the_index_too(self):
        import speasy as spz
        self.server.answer = lambda start, stop: Dataset('mfi', {'b': _hourly(start, stop)}, {})
        with self.index:
            spz.get_data('amda/some_dataset', _utc(2023, 1, 1), _utc(2023, 1, 2))
            self.assertIsInstance(spz.get_data('amda/some_dataset', _utc(2023, 1, 1), _utc(2023, 1, 2)), Dataset)
        self.assertEqual(len(self.server.calls), 1)
        self.direct.assert_not_called()
        self.index = DataIndex(self.index.path)

    def test_only_the_thread_that_entered_the_block(self):
        import threading
        import speasy as spz
        seen = []
        with self.index:
            thread = threading.Thread(target=lambda: seen.append(spz.get_data('ssc/ace', _utc(2023, 1, 1),
                                                                               _utc(2023, 1, 2))))
            thread.start()
            thread.join()
        self.assertEqual(seen, ['direct'])
        self.index = DataIndex(self.index.path)


class EveryProductKind(GetDataTestCase):
    def test_a_dataset_is_stored_by_day_and_served_trimmed(self):
        self.server.answer = lambda start, stop: Dataset('mfi', {'b': _hourly(start, stop), 'n': _hourly(start, stop, 2.)},
                                                         {'source': 'test'})
        self.get(_utc(2023, 1, 1), _utc(2023, 1, 3), product='amda/mfi')
        d = self.get(_utc(2023, 1, 1, 6), _utc(2023, 1, 2, 6), product='amda/mfi')
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual((d.name, d.meta, sorted(d.variables)), ('mfi', {'source': 'test'}, ['b', 'n']))
        self.assertEqual((len(d['b']), d['n'].values[0, 0]), (24, 2.))

    def test_a_timetable_is_stored_whole(self):
        first = self.index.get_data('amda/storms')
        again = self.index.get_data('amda/storms')
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual((again.name, list(again)), (first.name, list(first)))

    def test_a_catalog_is_stored_whole_with_its_events_meta(self):
        self.server.static_answer = lambda: Catalog('events', meta={'author': 'me'},
                                                    events=[Event(_utc(2023, 1, 1), _utc(2023, 1, 2), {'class': 'storm'})])
        self.index.get_data('amda/events')
        catalog = self.index.get_data('amda/events')
        self.assertEqual(len(self.server.calls), 1)
        self.assertEqual((catalog.meta, catalog[0].meta, catalog[0].start_time), ({'author': 'me'}, {'class': 'storm'},
                                                                                  _utc(2023, 1, 1)))

    def test_refresh_and_update_all_data_cover_timetables(self):
        self.index.get_data('amda/storms')
        self.index.get_data('amda/storms', refresh=True)
        self.index.update_all_data()
        self.assertEqual(len(self.server.calls), 3)
        self.assertTrue(all(c[3].get('force_refresh') for c in self.server.calls[1:]))


class SameArgumentsAsSpzGetData(GetDataTestCase):
    def test_a_time_range_tuple(self):
        self.assertEqual(len(self.index.get_data('ssc/ace', (_utc(2023, 1, 1), _utc(2023, 1, 2)))), 24)

    def test_several_products(self):
        a, b = self.index.get_data(['ssc/ace', 'ssc/wind'], _utc(2023, 1, 1), _utc(2023, 1, 2))
        self.assertEqual((len(a), len(b)), (24, 24))

    def test_several_ranges(self):
        found = self.index.get_data('ssc/ace', [(_utc(2023, 1, 1), _utc(2023, 1, 2)), (_utc(2023, 2, 1), _utc(2023, 2, 2))])
        self.assertEqual([len(v) for v in found], [24, 24])

    def test_a_timetable_as_the_ranges(self):
        found = self.index.get_data('ssc/ace', 'amda/storms')
        self.assertEqual([len(v) for v in found], [24])
        self.assertEqual(len(self.index.requests()), 2)   # the timetable is stored too

    def test_spz_get_data_is_back_to_normal_afterwards(self):
        import speasy.core.requests_scheduling.request_dispatch as dispatch
        self.index.get_data('ssc/ace', _utc(2023, 1, 1), _utc(2023, 1, 2))
        self.assertIsNone(dispatch.active_data_index.get())


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
