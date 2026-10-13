import json
import os
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

import numpy as np

from speasy.core.hapi.client import HapiClient
from speasy.core.hapi.exceptions import HapiRequestError

RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')

_TIME = {'name': 'Time', 'type': 'isotime', 'units': 'UTC', 'length': 24}
_SCALAR = {'name': 'scalar', 'type': 'double', 'units': 'nT'}
_LABEL = {'name': 'label', 'type': 'string', 'length': 4}
_INFO = {'HAPI': '3.3', 'startDate': '2000-01-01Z', 'stopDate': '2001-01-01Z',
         'parameters': [_TIME, _SCALAR, _LABEL]}


class _Response:
    def __init__(self, status_code=200, body=b''):
        self.status_code = status_code
        self.bytes = body if isinstance(body, bytes) else json.dumps(body).encode()

    @property
    def ok(self):
        return self.status_code < 400

    @property
    def text(self):
        return self.bytes.decode('utf-8')

    def json(self):
        return json.loads(self.text)


class _FakeServer:
    """Answers HAPI endpoints from canned bodies and records the queries it got."""

    def __init__(self, version='3.3', formats=('csv', 'binary'), data=b''):
        self.capabilities = {'HAPI': version, 'outputFormats': list(formats), 'status': {'code': 1200}}
        self.data = data
        self.queries = []

    def get(self, url, **kwargs):
        parsed = urlparse(url)
        endpoint = parsed.path.rsplit('/', 1)[-1]
        self.queries.append((parsed.path, {k: v[0] for k, v in parse_qs(parsed.query).items()}))
        if endpoint == 'capabilities':
            return _Response(body=self.capabilities)
        if endpoint == 'info':
            return _Response(body=_INFO)
        if endpoint == 'data':
            return self.data if isinstance(self.data, _Response) else _Response(body=self.data)
        return _Response(404, {'HAPI': '3.3', 'status': {'code': 1400, 'message': 'unknown'}})

    def last_data_query(self):
        return [q for path, q in self.queries if path.endswith('/data')][-1]


def _client(server, url='https://example.org/hapi'):
    with mock.patch('speasy.core.hapi.client.http.get', server.get):
        return HapiClient(url)


class TestHapiClientUrls(unittest.TestCase):
    def test_registry_urls_ending_in_hapi_are_used_as_is(self):
        server = _FakeServer()
        _client(server, 'https://example.org/some/hapi/')
        self.assertEqual(server.queries[0][0], '/some/hapi/capabilities')

    def test_server_roots_get_hapi_appended(self):
        server = _FakeServer()
        _client(server, 'https://example.org/service')
        self.assertEqual(server.queries[0][0], '/service/hapi/capabilities')

    def test_patch_versions_are_accepted(self):
        self.assertTrue(_client(_FakeServer(version='3.3.1')).is_v3)
        self.assertFalse(_client(_FakeServer(version='2.0')).is_v3)


class TestHapiClientData(unittest.TestCase):
    def _get_data(self, server, parameters=('scalar',), **kwargs):
        client = _client(server)
        with mock.patch('speasy.core.hapi.client.http.get', server.get):
            return client.get_data('ds', '2000-01-01T00:00:00Z', '2000-01-02T00:00:00Z', list(parameters),
                                   header=_INFO, **kwargs)

    def test_hapi_2_uses_id_and_time_min_max(self):
        server = _FakeServer(version='2.0', formats=('csv',))
        self._get_data(server)
        query = server.last_data_query()
        self.assertEqual(query['id'], 'ds')
        self.assertEqual((query['time.min'], query['time.max']), ('2000-01-01T00:00:00Z', '2000-01-02T00:00:00Z'))

    def test_hapi_3_uses_dataset_and_start_stop(self):
        server = _FakeServer(formats=('csv',))
        self._get_data(server)
        query = server.last_data_query()
        self.assertEqual(query['dataset'], 'ds')
        self.assertIn('start', query)

    def test_data_is_requested_without_header(self):
        server = _FakeServer(formats=('csv',))
        self._get_data(server)
        self.assertNotIn('include', server.last_data_query())

    def test_headerless_csv_is_decoded_with_the_given_header(self):
        server = _FakeServer(formats=('csv',), data=b'2000-01-01T00:00:00.000Z,1.5\n2000-01-01T00:00:01.000Z,2.5\n')
        v = self._get_data(server)['scalar']
        self.assertEqual(v.values[:, 0].tolist(), [1.5, 2.5])
        self.assertEqual(v.time[0], np.datetime64('2000-01-01T00:00:00'))
        self.assertEqual(v.unit, 'nT')

    def test_binary_is_preferred_when_offered(self):
        record = np.zeros(1, dtype=[('Time', 'S24'), ('scalar', '<f8')])
        record['Time'] = b'2000-01-01T00:00:00.000Z'
        record['scalar'] = 3.25
        server = _FakeServer(data=record.tobytes())
        v = self._get_data(server)['scalar']
        self.assertEqual(server.last_data_query()['format'], 'binary')
        self.assertEqual(v.values[0, 0], 3.25)

    def test_string_parameters_use_csv(self):
        server = _FakeServer(data=b'2000-01-01T00:00:00.000Z,abcd\n')
        self._get_data(server, parameters=('label',))
        self.assertEqual(server.last_data_query()['format'], 'csv')

    def test_empty_response_gives_an_empty_variable(self):
        v = self._get_data(_FakeServer(formats=('csv',), data=b''))['scalar']
        self.assertEqual(len(v), 0)

    def test_errors_raise_with_the_hapi_code(self):
        error = _Response(400, {'HAPI': '3.3', 'status': {'code': 1405, 'message': 'time outside valid range'}})
        with self.assertRaises(HapiRequestError) as ctx:
            self._get_data(_FakeServer(data=error))
        self.assertEqual(ctx.exception.code, 1405)

    def test_binary_body_is_not_decoded_as_json(self):
        record = np.zeros(1, dtype=[('Time', 'S24'), ('scalar', '<f8')])
        record['Time'] = b'2000-01-01T00:00:00.000Z'
        record['scalar'] = np.frombuffer(b'\xff' * 8, dtype='<f8')[0]
        self._get_data(_FakeServer(data=record.tobytes()))

    def test_header_defaults_to_info_of_requested_parameters(self):
        server = _FakeServer(formats=('csv',), data=b'2000-01-01T00:00:00.000Z,1.0\n')
        client = _client(server)
        with mock.patch('speasy.core.hapi.client.http.get', server.get):
            v = client.get_data('ds', '2000-01-01T00:00:00Z', '2000-01-02T00:00:00Z', ['scalar'])['scalar']
        self.assertEqual(v.unit, 'nT')


if __name__ == '__main__':
    unittest.main()
