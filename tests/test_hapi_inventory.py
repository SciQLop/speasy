import json
import os
import unittest

from speasy.core.hapi.inventory import build_inventory
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
        self.assertEqual(self.dataset.start_date, '1970-01-01Z')
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


if __name__ == '__main__':
    unittest.main()
