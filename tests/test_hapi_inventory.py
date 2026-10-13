import json
import os
import unittest

import threading
from datetime import timedelta
from unittest import mock

from speasy.core.hapi.inventory import (HapiDatasetIndex, HapiServerIndex, build_inventory, fill_dataset,
                                        iso8601_duration, load_into, normalized_time)
from speasy.core.inventory import ProviderInventory
from speasy.core.inventory.indexes import (DatasetIndex, ParameterIndex, SpeasyIndex, from_dict, to_dict)

RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'hapi_inventory')
PROVIDER = 'hapi'
SERVER = 'test'


def _load(name):
    with open(os.path.join(RESOURCES, name)) as f:
        return json.load(f)


def _build(catalog, server_meta=None):
    root = SpeasyIndex(name=SERVER, provider=PROVIDER, uid=SERVER)
    return build_inventory(root, server_meta or {}, catalog)


def _flat(root):
    flat = ProviderInventory()
    flat.update(root)
    return flat


def _hapi_2_0_catalog():
    return [dict(entry, info=_load(f"TestData2.0_info_{entry['id']}.json"))
            for entry in _load('TestData2.0_catalog.json')['catalog']]


class TestHapi33DepthAll(unittest.TestCase):
    def setUp(self):
        self.root = _build(_load('TestData3.3_catalog_all.json')['catalog'],
                           {'HAPI': '3.3', 'outputFormats': ['csv', 'binary']})
        self.dataset = self.root.dataset1

    def test_server_meta_is_on_root(self):
        self.assertEqual(self.root.HAPI, '3.3')
        self.assertEqual(self.root.outputFormats, ['csv', 'binary'])

    def test_datasets_are_dataset_indexes_with_raw_uid(self):
        self.assertIsInstance(self.dataset, DatasetIndex)
        self.assertEqual(self.dataset.spz_uid(), 'test/dataset1')
        self.assertEqual(self.dataset.spz_provider(), PROVIDER)

    def test_dataset_dates_are_speasy_ranges(self):
        self.assertEqual(self.dataset.start_date, '1970-01-01T00:00Z')
        self.assertEqual(self.dataset.stop_date, self.dataset.stopDate)

    def test_hapi_fields_are_kept_verbatim(self):
        self.assertEqual(self.dataset.cadence, 'PT1S')
        self.assertIn('additionalMetadata', self.dataset.__dict__)
        self.assertNotIn('parameters', self.dataset.__dict__)

    def test_time_column_has_no_parameter(self):
        self.assertEqual([p.spz_name() for p in self.dataset], ['vector'])

    def test_parameter_uid_and_meta(self):
        vector = self.dataset.vector
        self.assertIsInstance(vector, ParameterIndex)
        self.assertEqual(vector.spz_uid(), 'test/dataset1/vector')
        self.assertEqual(vector.size, [3])
        self.assertEqual(vector.units, 'm')
        self.assertEqual(vector.start_date, self.dataset.start_date)
        self.assertEqual(vector.stop_date, self.dataset.stop_date)
        self.assertEqual(vector.dataset, 'test/dataset1')

    def test_parameter_name_with_space_keeps_raw_uid(self):
        parameter = self.root.dataset3.vector_parameter
        self.assertEqual(parameter.spz_uid(), 'test/dataset3/vector parameter')

    def test_hapi_description_is_kept(self):
        self.assertEqual(self.dataset.description, 'A sample dataset containing a vector parameter.')

    def test_flat_inventory_lookup_by_raw_ids(self):
        flat = _flat(self.root)
        self.assertIs(flat.datasets['test/dataset3'], self.root.dataset3)
        self.assertIs(flat.parameters['test/dataset3/vector parameter'], self.root.dataset3.vector_parameter)

    def test_round_trips_through_dict(self):
        self.assertEqual(from_dict(to_dict(self.root, version=2), version=2), self.root)


class TestHapi20Infos(unittest.TestCase):
    def setUp(self):
        self.root = _build(_hapi_2_0_catalog())

    def test_info_status_and_version_are_dropped(self):
        self.assertNotIn('status', self.root.dataset1.__dict__)
        self.assertNotIn('HAPI', self.root.dataset1.__dict__)

    def test_all_non_time_parameters_are_listed(self):
        self.assertEqual(len(list(self.root.dataset1)), 17)

    def test_title_kept_and_used_as_description_when_missing(self):
        self.assertEqual(self.root.dataset2.title, 'Dataset w/valid HAPI 2.0 - Same as dataset1 but at PT1H resolution')
        self.assertEqual(self.root.dataset2.description, self.root.dataset2.title)

    def test_bins_are_kept(self):
        self.assertEqual(self.root.dataset1.spectra.bins[0]['name'], 'frequency')


class TestCatalogWithoutInfo(unittest.TestCase):
    def test_dataset_without_info_has_only_its_title(self):
        root = _build([{'id': 'ds', 'title': 'A dataset'}])
        self.assertIsInstance(root.ds, DatasetIndex)
        self.assertEqual(root.ds.title, 'A dataset')
        self.assertEqual(list(root.ds), [])


def _info(*names):
    return {'startDate': '2000-01-01Z', 'stopDate': '2001-01-01Z',
            'parameters': [{'name': 'Time', 'type': 'isotime'}] + [{'name': n, 'type': 'double'} for n in names]}


class TestIdentifiers(unittest.TestCase):
    def test_slashes_in_dataset_ids_become_levels(self):
        root = _build([{'id': 'data/IBEX/ENA/AVG5MIN', 'title': 't', 'info': _info('flux')},
                       {'id': 'data/IBEX/ENA/AVG1H', 'title': 't', 'info': _info('flux')}])
        ena = root.data.IBEX.ENA
        self.assertIsInstance(ena, SpeasyIndex)
        self.assertEqual(ena.spz_uid(), 'test/data/IBEX/ENA')
        self.assertEqual(ena.AVG5MIN.spz_uid(), 'test/data/IBEX/ENA/AVG5MIN')
        self.assertEqual(ena.AVG1H.flux.spz_uid(), 'test/data/IBEX/ENA/AVG1H/flux')

    def test_colliding_parameter_names_are_all_kept(self):
        root = _build([{'id': 'ds', 'title': 't', 'info': _info('a b', 'a_b')}])
        self.assertEqual(sorted(p.spz_uid() for p in root.ds), ['test/ds/a b', 'test/ds/a_b'])

    def test_parameter_named_like_a_hapi_field_does_not_clobber_it(self):
        root = _build([{'id': 'ds', 'title': 't', 'info': _info('cadence') | {'cadence': 'PT1S'}}])
        self.assertEqual(root.ds.cadence, 'PT1S')
        self.assertEqual([p.spz_uid() for p in root.ds], ['test/ds/cadence'])

    def test_dataset_named_like_a_server_field_does_not_clobber_it(self):
        root = _build([{'id': 'HAPI', 'title': 't', 'info': _info('x')}], {'HAPI': '3.3'})
        self.assertEqual(root.HAPI, '3.3')
        self.assertEqual(_flat(root).datasets['test/HAPI'].spz_uid(), 'test/HAPI')


class TestTimes(unittest.TestCase):
    def test_hapi_time_forms_become_iso(self):
        self.assertEqual(normalized_time('1970-01-01Z'), '1970-01-01T00:00Z')
        self.assertEqual(normalized_time('2015-032T01:02:03.5Z'), '2015-02-01T01:02:03.5Z')
        self.assertEqual(normalized_time('2015-032Z'), '2015-02-01T00:00Z')
        self.assertEqual(normalized_time('2024-01-01T00:00Z'), '2024-01-01T00:00Z')

    def test_dataset_dates_are_normalized(self):
        root = _build([{'id': 'ds', 'info': {**_info('x'), 'startDate': '2015-032Z'}}])
        self.assertEqual(root.ds.start_date, '2015-02-01T00:00Z')
        self.assertEqual(root.ds.startDate, '2015-032Z')
        self.assertEqual(root.ds.x.start_date, '2015-02-01T00:00Z')

    def test_durations(self):
        self.assertEqual(iso8601_duration('P366D'), timedelta(days=366))
        self.assertEqual(iso8601_duration('PT1H30M'), timedelta(hours=1, minutes=30))
        self.assertEqual(iso8601_duration('P1M'), timedelta(days=28))
        self.assertEqual(iso8601_duration('P2Y'), timedelta(days=730))
        self.assertEqual(iso8601_duration('PT0.5S'), timedelta(seconds=0.5))
        self.assertIsNone(iso8601_duration('soon'))
        self.assertIsNone(iso8601_duration(None))


class TestRolledOverTimes(unittest.TestCase):
    def test_hour_24_is_the_next_day(self):
        self.assertEqual(normalized_time('2016-01-31T24:00:00.000Z'), '2016-02-01T00:00Z')
        self.assertEqual(normalized_time('2015-365T24:00Z'), '2016-01-01T00:00Z')

    def test_leap_second_is_the_next_minute(self):
        self.assertEqual(normalized_time('1998-12-31T23:59:60Z'), '1999-01-01T00:00Z')
        self.assertEqual(normalized_time('1998-12-31T23:59:60.5Z'), '1999-01-01T00:00Z')


class TestMissingDates(unittest.TestCase):
    def _lazy_build(self, catalog):
        return build_inventory(SpeasyIndex(name=SERVER, provider=PROVIDER, uid=SERVER), {}, catalog,
                               dataset_type=HapiDatasetIndex)

    def test_depth_all_entry_without_dates_does_not_hide_the_others(self):
        root = self._lazy_build([{'id': 'bad', 'info': {**_info('x'), 'startDate': None}},
                                 {'id': 'missing', 'info': {'parameters': _info('x')['parameters']}},
                                 {'id': 'good', 'info': _info('x')}])
        self.assertIn('x', root.__dict__['good'].__dict__)
        self.assertFalse(root.__dict__['bad'].__dict__['hapi_loaded'])
        self.assertFalse(root.__dict__['missing'].__dict__['hapi_loaded'])

    def test_info_without_dates_says_what_is_wrong(self):
        dataset = DatasetIndex(name='bad', provider=PROVIDER, uid='test/bad')
        info = {**_info('x'), 'stopDate': None}
        with self.assertRaisesRegex(ValueError, r"(?s)'test/bad'.*startDate.*stopDate.*server"):
            fill_dataset(dataset, info)


class TestTimeParameter(unittest.TestCase):
    def test_time_column_is_kept_on_the_dataset(self):
        root = _build([{'id': 'ds', 'info': _info('x')}])
        self.assertEqual(root.ds.time_parameter, {'name': 'Time', 'type': 'isotime'})


class _Loader:
    def __init__(self, fill):
        self.fill = fill
        self.calls = 0

    def __call__(self, node):
        self.calls += 1
        load_into(node, self.fill)


class TestLazyNodes(unittest.TestCase):
    def setUp(self):
        from speasy.core.hapi import inventory
        inventory._failed_loads.clear()
        self._saved = HapiServerIndex.loader, HapiDatasetIndex.loader
        self.server_loader = _Loader(lambda node: build_inventory(
            node, {'HAPI': '3.3'}, [{'id': 'ds', 'title': 't'}], dataset_type=HapiDatasetIndex))
        self.dataset_loader = _Loader(lambda node: build_inventory(node, {}, []) and None)
        HapiServerIndex.loader = self.server_loader
        HapiDatasetIndex.loader = self.dataset_loader

    def tearDown(self):
        HapiServerIndex.loader, HapiDatasetIndex.loader = self._saved

    def _server(self):
        return HapiServerIndex(name=SERVER, provider=PROVIDER, uid=SERVER)

    def test_server_loads_on_first_missing_attribute_only(self):
        server = self._server()
        self.assertEqual(self.server_loader.calls, 0)
        self.assertIsInstance(server.ds, HapiDatasetIndex)
        server.ds
        self.assertEqual(self.server_loader.calls, 1)
        self.assertTrue(server.hapi_loaded)

    def test_dir_loads(self):
        self.assertIn('ds', dir(self._server()))

    def test_private_names_never_load(self):
        server = self._server()
        self.assertFalse(hasattr(server, '_repr_html_'))
        self.assertEqual(self.server_loader.calls, 0)

    def test_unknown_name_after_load_is_attribute_error(self):
        with self.assertRaises(AttributeError):
            self._server().nope

    def test_failed_load_is_attribute_error_and_retried(self):
        def broken(node):
            raise RuntimeError('server down')
        HapiServerIndex.loader = broken
        server = self._server()
        self.assertFalse(hasattr(server, 'ds'))
        HapiServerIndex.loader = self.server_loader
        with mock.patch('speasy.core.hapi.inventory.FAILED_LOAD_BACKOFF', 0):
            self.assertIsInstance(server.ds, HapiDatasetIndex)

    def test_implicit_loads_back_off_after_a_failure(self):
        failing = _Loader(lambda node: (_ for _ in ()).throw(RuntimeError('server down')))
        HapiServerIndex.loader = failing
        server = self._server()
        for _ in range(3):
            self.assertFalse(hasattr(server, 'ds'))
        self.assertEqual(failing.calls, 1)

    def test_explicit_loads_ignore_the_back_off(self):
        failing = _Loader(lambda node: (_ for _ in ()).throw(RuntimeError('server down')))
        HapiServerIndex.loader = failing
        server = self._server()
        self.assertFalse(hasattr(server, 'ds'))
        with self.assertRaises(RuntimeError):
            server._load()
        self.assertEqual(failing.calls, 2)

    def test_dataset_loads_on_iteration_and_membership(self):
        def fill(node):
            from speasy.core.hapi.inventory import fill_dataset
            fill_dataset(node, _info('x'))
        HapiDatasetIndex.loader = _Loader(fill)
        ds = self._server().ds
        self.assertEqual([p.spz_uid() for p in ds], ['test/ds/x'])
        self.assertIn('test/ds/x', ds)
        self.assertEqual(HapiDatasetIndex.loader.calls, 1)

    def test_entries_with_info_are_loaded_datasets(self):
        root = _build([{'id': 'ds', 'info': _info('x')}, {'id': 'lazy'}])
        self.assertIsInstance(root.ds, DatasetIndex)
        self.assertNotIsInstance(root.ds, HapiDatasetIndex)
        root = build_inventory(SpeasyIndex(name=SERVER, provider=PROVIDER, uid=SERVER), {},
                               [{'id': 'ds', 'info': _info('x')}, {'id': 'lazy'}], dataset_type=HapiDatasetIndex)
        self.assertTrue(root.ds.hapi_loaded)
        self.assertFalse(root.lazy.hapi_loaded)

    def test_load_swaps_the_dict_so_iterating_readers_never_see_it_change(self):
        server = self._server()
        before = server.__dict__
        server.ds
        self.assertIsNot(server.__dict__, before)
        self.assertNotIn('ds', before)

    def test_lazy_nodes_round_trip_through_dict(self):
        server = self._server()
        server.ds
        restored = from_dict(to_dict(server, version=2), version=2)
        self.assertIsInstance(restored, HapiServerIndex)
        self.assertIsInstance(restored.__dict__['ds'], HapiDatasetIndex)
        self.assertTrue(restored.hapi_loaded)

    def test_concurrent_first_access_loads_once(self):
        gate = threading.Event()

        def slow_fill(node):
            gate.wait(1)
            build_inventory(node, {}, [{'id': 'ds'}], dataset_type=HapiDatasetIndex)
        HapiServerIndex.loader = _Loader(slow_fill)
        server = self._server()
        results = []
        threads = [threading.Thread(target=lambda: results.append(server.ds)) for _ in range(8)]
        for t in threads:
            t.start()
        gate.set()
        for t in threads:
            t.join()
        self.assertEqual(HapiServerIndex.loader.calls, 1)
        self.assertEqual(len(results), 8)


if __name__ == '__main__':
    unittest.main()
