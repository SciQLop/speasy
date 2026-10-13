"""HAPI provider logic against a fake HapiClient serving recorded responses: no network access."""
import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import mock

import numpy as np

from speasy.core.data_containers import DataContainer, VariableTimeAxis
from speasy.core.hapi.exceptions import HapiRequestError
from speasy.core.hapi.inventory import HapiDatasetIndex, HapiServerIndex
from speasy.core.hapi.registry import enabled_servers, server_key
from speasy.core import dataprovider
from speasy.core.requests_scheduling import request_dispatch
from speasy.inventories import flat_inventories, tree
from speasy.products import SpeasyVariable

RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'hapi_inventory')


def _load(name):
    with open(os.path.join(RESOURCES, name)) as f:
        return json.load(f)


def _slashed_info(max_duration=None):
    info = {'startDate': '2000-01-01Z', 'stopDate': '2001-01-01Z',
            'parameters': [{'name': 'Time', 'type': 'isotime', 'length': 24},
                           {'name': 'Field/X', 'type': 'double', 'units': 'nT'}]}
    if max_duration:
        info['maxRequestDuration'] = max_duration
    return info


SERVERS = {
    'https://fake/v2/hapi': {
        'capabilities': {'HAPI': '2.0', 'outputFormats': ['csv'], 'status': {'code': 1200}},
        'catalog': _load('TestData2.0_catalog.json')['catalog'],
        'infos': {d: _load(f'TestData2.0_info_{d}.json') for d in ('dataset1', 'dataset2', 'dataset3')},
    },
    'https://fake/v3/hapi': {
        'capabilities': {'HAPI': '3.3', 'outputFormats': ['csv', 'binary'], 'catalogDepthOptions': ['dataset', 'all'],
                         'status': {'code': 1200}},
        'catalog': _load('TestData3.3_catalog_all.json')['catalog'],
        'about': {'HAPI': '3.3', 'id': 'TestData3.3', 'contact': 'someone', 'status': {'code': 1200}},
    },
    'https://fake/slashed/hapi': {
        'capabilities': {'HAPI': '3.1', 'outputFormats': ['csv'], 'status': {'code': 1200}},
        'catalog': [{'id': 'aaa/PT1M/xyz', 'title': 'one minute'}, {'id': 'aaa/PT1H/xyz', 'title': 'one hour'}],
        'infos': {'aaa/PT1M/xyz': _slashed_info('P10D'), 'aaa/PT1H/xyz': _slashed_info()},
    },
}

REGISTRY = [
    {'id': 'V2', 'title': 'HAPI 2 test server', 'x_url': 'https://fake/v2/hapi'},
    {'id': 'V3', 'title': 'HAPI 3 test server', 'x_url': 'https://fake/v3/hapi'},
    {'id': 'Slashed', 'title': 'ids with slashes', 'x_url': 'https://fake/slashed/hapi'},
    {'id': 'Down', 'title': 'unreachable', 'x_url': 'https://fake/down/hapi'},
    {'id': 'CDAWeb', 'title': 'natively served', 'x_url': 'https://fake/cdaweb/hapi'},
]


class FakeClient:
    instances = []

    def __init__(self, url):
        if url not in SERVERS:
            raise ConnectionError(f"{url} is unreachable")
        self.server = SERVERS[url]
        self.base_url = url
        self.capabilities = self.server['capabilities']
        self.is_v3 = self.capabilities['HAPI'].startswith('3')
        self.calls = []
        FakeClient.instances.append(self)

    def get_catalog(self, depth=None):
        self.calls.append(('catalog', depth))
        if depth == 'all':
            return {'catalog': self.server['catalog']}
        return {'catalog': [{k: v for k, v in e.items() if k != 'info'} for e in self.server['catalog']]}

    def get_about(self):
        self.calls.append(('about',))
        if 'about' not in self.server:
            raise HapiRequestError(1400, 'no /about here')
        return self.server['about']

    def get_info(self, dataset, parameters=None):
        self.calls.append(('info', dataset))
        return self.server['infos'][dataset]

    def get_data(self, dataset, start, stop, parameters, header=None, headers=None):
        self.calls.append(('data', dataset, start, stop, tuple(parameters), header))
        t0, t1 = (np.datetime64(t.rstrip('Z'), 'ns') for t in (start, stop))
        times = np.arange(t0, t1, np.timedelta64(1, 'h'))
        return {p: SpeasyVariable(axes=[VariableTimeAxis(values=times)],
                                  values=DataContainer(np.arange(len(times), dtype=float), name=p))
                for p in parameters}

    @classmethod
    def calls_of(cls, kind):
        return [c for client in cls.instances for c in client.calls if c[0] == kind]


@contextmanager
def _hapi_provider(registry=REGISTRY, disabled=('cdaweb',), extra=None, client=FakeClient):
    """A HapiWebservice using ``client`` (FakeClient by default); the global provider state is restored afterwards."""
    from speasy.data_providers import hapi
    namespaces = (tree.__dict__, flat_inventories.__dict__, request_dispatch.PROVIDERS, dataprovider.PROVIDERS)
    saved = [namespace.get('hapi') for namespace in namespaces]
    saved_loaders = HapiServerIndex.loader, HapiDatasetIndex.loader
    FakeClient.instances = []
    servers = enabled_servers(registry, set(disabled), extra or {})
    with mock.patch.object(hapi, 'HapiClient', client), \
            mock.patch.object(hapi, '_server_records', return_value=servers):
        try:
            provider = request_dispatch.PROVIDERS['hapi'] = hapi.HapiWebservice()
            yield provider
        finally:
            for namespace, value in zip(namespaces, saved):
                namespace.pop('hapi', None)
                if value is not None:
                    namespace['hapi'] = value
            HapiServerIndex.loader, HapiDatasetIndex.loader = saved_loaders


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class TestRegistry(unittest.TestCase):
    def test_keys_are_python_names(self):
        self.assertEqual(server_key('UCalgary/SRS'), 'ucalgary_srs')
        self.assertEqual(server_key('WDC-Kyoto-HAPI'), 'wdc_kyoto_hapi')

    def test_disabled_servers_are_dropped_whatever_their_spelling(self):
        self.assertNotIn('cdaweb', enabled_servers(REGISTRY, {'CDAWeb'}, {}))

    def test_extra_servers_are_added_under_their_key(self):
        servers = enabled_servers([], set(), {'MyLab': 'https://lab.example/hapi'})
        self.assertEqual(servers['mylab']['x_url'], 'https://lab.example/hapi')

    def test_bundled_registry_is_the_official_list(self):
        from speasy.core.hapi.registry import bundled_registry
        keys = {server_key(e['id']) for e in bundled_registry()}
        self.assertTrue({'cdaweb', 'amda', 'csa', 'sscweb', 'lisird', 'knmi', 'intermagnet'} <= keys)

    def test_natively_served_servers_are_disabled_by_default(self):
        import speasy.config as cfg
        entry = cfg.hapi.disabled_servers
        self.assertEqual(entry.type_ctor(entry.default), {'cdaweb', 'amda', 'csa', 'sscweb'})


class TestServerNodes(unittest.TestCase):
    def test_starting_the_provider_contacts_no_server(self):
        with _hapi_provider():
            self.assertEqual(FakeClient.instances, [])
            self.assertIsInstance(tree.hapi.__dict__['v2'], HapiServerIndex)

    def test_disabled_servers_have_no_node(self):
        with _hapi_provider():
            self.assertNotIn('cdaweb', tree.hapi.__dict__)

    def test_extra_servers_have_a_node(self):
        with _hapi_provider(extra={'mylab': 'https://fake/v3/hapi'}):
            self.assertIn('vector', dir(tree.hapi.mylab.dataset1))

    def test_registry_record_is_kept_on_the_server_node(self):
        with _hapi_provider():
            self.assertEqual(tree.hapi.__dict__['v2'].title, 'HAPI 2 test server')

    def test_server_without_depth_all_lists_lazy_datasets(self):
        with _hapi_provider():
            dataset = tree.hapi.v2.dataset1
            self.assertIsInstance(dataset, HapiDatasetIndex)
            self.assertEqual(FakeClient.calls_of('info'), [])
            self.assertIn('spectra', dir(dataset))
            self.assertEqual(FakeClient.calls_of('info'), [('info', 'dataset1')])

    def test_server_with_depth_all_is_loaded_in_one_request(self):
        with _hapi_provider():
            self.assertEqual(tree.hapi.v3.dataset1.vector.units, 'm')
            self.assertEqual(FakeClient.calls_of('catalog'), [('catalog', 'all')])
            self.assertEqual(FakeClient.calls_of('info'), [])

    def test_server_meta_comes_from_capabilities_and_about(self):
        with _hapi_provider():
            server = tree.hapi.v3
            self.assertEqual((server.HAPI, server.contact), ('3.3', 'someone'))
            self.assertNotIn('status', server.__dict__)

    def test_broken_about_does_not_hide_the_server(self):
        with _hapi_provider():
            self.assertIn('aaa', dir(tree.hapi.slashed))

    def test_hapi_2_servers_get_no_about_request(self):
        with _hapi_provider():
            tree.hapi.v2.dataset1
            self.assertEqual(FakeClient.calls_of('about'), [])

    def test_loaded_nodes_are_in_the_flat_inventory(self):
        with _hapi_provider() as provider:
            tree.hapi.v2.dataset1.scalar
            self.assertIn('v2/dataset1', provider.flat_inventory.datasets)
            self.assertIn('v2/dataset1/scalar', provider.flat_inventory.parameters)

    def test_unreachable_server_has_no_children_and_is_retried(self):
        with _hapi_provider():
            self.assertFalse(hasattr(tree.hapi.down, 'anything'))
            self.assertFalse(hasattr(tree.hapi.down, 'anything'))


class TestGetData(unittest.TestCase):
    def _get(self, product, start=_utc(2010, 1, 1), stop=_utc(2010, 1, 2), **kwargs):
        return request_dispatch.get_data(f"hapi/{product}", start, stop, disable_cache=True, **kwargs)

    def test_get_data_resolves_unloaded_products(self):
        with _hapi_provider():
            v = self._get('v2/dataset1/scalar')
            self.assertEqual(len(v), 24)
            self.assertEqual(FakeClient.calls_of('info'), [('info', 'dataset1')])

    def test_data_request_carries_the_time_column_and_parameter_header(self):
        with _hapi_provider():
            self._get('v2/dataset1/scalar')
            _, dataset, start, stop, parameters, header = FakeClient.calls_of('data')[0]
            self.assertEqual((dataset, parameters), ('dataset1', ('scalar',)))
            self.assertEqual((start, stop), ('2010-01-01T00:00:00Z', '2010-01-02T00:00:00Z'))
            self.assertEqual([p['name'] for p in header['parameters']], ['Time', 'scalar'])
            self.assertEqual(header['parameters'][1]['units'], 'm')
            self.assertNotIn('start_date', header['parameters'][1])

    def test_slashes_in_dataset_ids_and_parameter_names(self):
        with _hapi_provider():
            self._get('slashed/aaa/PT1H/xyz/Field/X', _utc(2000, 2, 1), _utc(2000, 2, 2))
            self.assertEqual(FakeClient.calls_of('data')[0][1:2], ('aaa/PT1H/xyz',))

    def test_parameter_index_works_like_its_path(self):
        with _hapi_provider():
            v = request_dispatch.get_data(tree.hapi.v3.dataset1.vector, _utc(1970, 1, 1), _utc(1970, 1, 1, 1),
                                          disable_cache=True)
            self.assertEqual(len(v), 1)

    def test_long_requests_are_split_on_max_request_duration(self):
        with _hapi_provider():
            v = self._get('slashed/aaa/PT1M/xyz/Field/X', _utc(2000, 1, 1), _utc(2000, 1, 26))
            self.assertEqual([c[2] for c in FakeClient.calls_of('data')],
                             ['2000-01-01T00:00:00Z', '2000-01-11T00:00:00Z', '2000-01-21T00:00:00Z'])
            self.assertEqual(len(v), 25 * 24)

    def test_requests_are_clamped_to_the_dataset_range(self):
        with _hapi_provider():
            self._get('slashed/aaa/PT1H/xyz/Field/X', _utc(2000, 12, 31, 12), _utc(2001, 1, 2))
            self.assertEqual(FakeClient.calls_of('data')[0][2:4], ('2000-12-31T12:00:00Z', '2001-01-01T00:00:00Z'))

    def test_requests_outside_the_dataset_range_return_none(self):
        with _hapi_provider():
            self.assertIsNone(self._get('slashed/aaa/PT1H/xyz/Field/X', _utc(2005, 1, 1), _utc(2005, 1, 2)))
            self.assertEqual(FakeClient.calls_of('data'), [])

    def test_disable_proxy_is_accepted(self):
        with _hapi_provider():
            self.assertIsNotNone(self._get('v2/dataset1/scalar', disable_proxy=True))

    def test_unknown_server_error_says_how_to_add_one(self):
        with _hapi_provider():
            with self.assertRaisesRegex(ValueError, r"(?s)Unknown HAPI server 'nope'.*v2.*extra_servers"):
                self._get('nope/ds/p')

    def test_disabled_server_error_says_how_to_enable_it(self):
        with _hapi_provider():
            with self.assertRaisesRegex(ValueError, r"(?s)'cdaweb' is disabled.*disabled_servers"):
                self._get('cdaweb/ds/p')

    def test_unknown_parameter_error_names_it(self):
        with _hapi_provider():
            with self.assertRaisesRegex(ValueError, r"Unknown parameter.*v2/dataset1/nope"):
                self._get('v2/dataset1/nope')

    def test_unreachable_server_error_is_raised(self):
        with _hapi_provider():
            with self.assertRaisesRegex(ConnectionError, 'unreachable'):
                self._get('down/ds/p')


TEST_SERVERS = [{'id': 'TestData2.0', 'x_url': 'https://hapi-server.org/servers/TestData2.0/hapi'},
                {'id': 'TestData3.3', 'x_url': 'https://hapi-server.org/servers/TestData3.3/hapi'}]


class TestLiveTestDataServers(unittest.TestCase):
    """The real HapiClient against the HAPI project's test servers."""

    def _provider(self):
        from speasy.core.hapi.client import HapiClient
        return _hapi_provider(registry=TEST_SERVERS, disabled=(), client=HapiClient)

    def test_hapi_2_spectra_with_bins(self):
        with self._provider():
            v = request_dispatch.get_data('hapi/testdata2_0/dataset1/spectra', _utc(1970, 1, 1), _utc(1970, 1, 1, 0, 1),
                                          disable_cache=True)
            self.assertEqual(v.values.shape, (50, 10))  # the server has a 10 s gap in this minute
            self.assertEqual(len(v.axes), 2)

    def test_hapi_3_binary_vector(self):
        with self._provider():
            v = request_dispatch.get_data(tree.hapi.testdata3_3.dataset1.vector, _utc(1970, 1, 1),
                                          _utc(1970, 1, 1, 0, 1), disable_cache=True)
            self.assertEqual(v.values.shape, (60, 3))
            self.assertEqual(v.unit, 'm')

    def test_parameter_names_with_spaces(self):
        with self._provider():
            v = request_dispatch.get_data('hapi/testdata3_3/dataset3/vector parameter', _utc(1970, 1, 1),
                                          _utc(1970, 1, 1, 0, 1), disable_cache=True)
            self.assertEqual(v.values.shape, (60, 3))

    def test_cached_requests_give_the_same_data(self):
        with self._provider():
            args = 'hapi/testdata3_3/dataset1/vector', _utc(1970, 1, 1), _utc(1970, 1, 1, 0, 2)
            first = request_dispatch.get_data(*args)
            second = request_dispatch.get_data(*args)
            self.assertEqual(len(first), 60)  # the server has no record after 00:00:59
            self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
