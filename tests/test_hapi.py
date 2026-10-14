import unittest
from ddt import data, ddt, unpack

from speasy.core.hapi.client import HapiClient, HapiEndpoint
from speasy.core.hapi.provider import HapiProvider
from speasy.core.hapi.exceptions import HapiRequestError, HapiServerError, HapiNoData
from speasy.products.variable import SpeasyVariable


HAPITEST33_SERVER_ROOT = "https://hapi-server.org/servers/TestData3.3"
HAPITEST20_SERVER_ROOT = "https://hapi-server.org/servers/TestData2.0"
# The HAPI test servers have no per-component labels, the BGS World Data Centre does.
BGS_WDC_SERVER_ROOT = "https://wdcapi.bgs.ac.uk/hapi"

@ddt
class TestHapiClient(unittest.TestCase):

    def test_build_url(self):
        hapi_client = HapiClient(HAPITEST33_SERVER_ROOT)
        about_url = hapi_client._build_url(endpoint=HapiEndpoint.ABOUT)
        self.assertEqual(f"{HAPITEST33_SERVER_ROOT}/hapi/about", about_url)

    def test_get_info_bad_dataset(self):
        hapi_client = HapiClient(HAPITEST33_SERVER_ROOT)
        with self.assertRaises(HapiRequestError) as rc:
            hapi_client.get_info('wrong_dataset_name')
        self.assertEqual(1406, rc.exception.code)

    def test_get_info_bad_parameter(self):
        hapi_client = HapiClient(HAPITEST33_SERVER_ROOT)
        with self.assertRaises(HapiRequestError) as rc:
            hapi_client.get_info('dataset1', ['wrong_parameter'])
        self.assertEqual(1407, rc.exception.code)

    @data(
            ('dataset1', '1970-01-02', '1970-01-01', [], 1404 ), # start time >= stop time
            ('dataset1', '1970-01-01', '1970-01-02', [], 1405 ), # times outside valid ranges
            ('wrong_dataset_name', '1970-01-01', '1970-01-02', [], 1406 ), # wrong dataset id
            ('dataset1', '1970-01-01', '1970-01-02', ['no_such_parameter'], 1407 ) # wrong dataset parameter id
    )
    @unpack
    def test_get_data_bad_request(self, dataset, start, stop, parameters, expected_err_code):
        hapi_client = HapiClient(HAPITEST33_SERVER_ROOT)
        with self.assertRaises(HapiRequestError) as rc:
            hapi_client.get_data(dataset, start, stop, parameters)
        self.assertEqual(expected_err_code, rc.exception.code)

    def test_get_data_good_request(self):
        hapi_client = HapiClient(HAPITEST33_SERVER_ROOT)
        result = hapi_client.get_data('dataset1', '1970-01-01Z', '1970-01-01T00:01:11Z', ['vector'])
        self.assertIsInstance(result['vector'], SpeasyVariable)

    def test_labels_become_column_names(self):
        hapi_client = HapiClient(BGS_WDC_SERVER_ROOT)
        result = hapi_client.get_data('aaa/PT1M/xyz', '2010-01-01T00:00Z', '2010-01-01T00:10Z', ['Field_Vector'])
        self.assertEqual(['X', 'Y', 'Z'], result['Field_Vector'].columns)


@ddt
class TestHapiProvider(unittest.TestCase):

    def test_capabilities(self):
        hapi_provider = HapiProvider(HAPITEST20_SERVER_ROOT)
        result = hapi_provider.capabilities()
        self.assertEqual("2.0", result["HAPI"])
        self.assertCountEqual( result["outputFormats"], ['json', 'csv', 'binary'])

    def test_about(self):
        hapi_provider = HapiProvider(HAPITEST33_SERVER_ROOT)
        result = hapi_provider.about()
        self.assertEqual("3.3", result["HAPI"])
        self.assertEqual(1200, result["status"]["code"])
        self.assertIsInstance(result["note"], list)

    @data (
        (HAPITEST33_SERVER_ROOT, ["data", "info"]),
        (HAPITEST20_SERVER_ROOT, ["data", "info"]),
    )
    @unpack
    def test_hapi(self, root_url, contents):
        hapi_provider = HapiProvider(root_url)
        html_hapi = hapi_provider.hapi()
        self.assertIn("<html", html_hapi.lower())
        for c in contents:
            self.assertIn(c, html_hapi)

    @data (
        (HAPITEST33_SERVER_ROOT,),
        (HAPITEST20_SERVER_ROOT,)
    )
    @unpack
    def test_catalog(self, root_url):
        hapi_provider = HapiProvider(root_url)
        data = hapi_provider.catalog()

        self.assertIn("catalog", data)
        self.assertIsInstance(data["catalog"], list)
        for item in data["catalog"][-2:-1]:
            self.assertIn("id", item)

        self.assertIn("HAPI", data)

        self.assertIn("status", data)
        self.assertEqual(1200, data["status"]["code"])
        self.assertEqual("ok", data["status"]["message"].lower())

    @data(
        (HAPITEST33_SERVER_ROOT,"dataset1", 2),
        (HAPITEST20_SERVER_ROOT, "dataset1", 18),
    )
    @unpack
    def test_info_dataset_only(self, root_url, dataset, nb_params):
        hapi_provider = HapiProvider(root_url)
        data = hapi_provider.info(dataset)
        self.assertIn("HAPI", data)
        self.assertIn("parameters", data)
        self.assertEqual(nb_params, len(data['parameters']))

    @data(
        (HAPITEST33_SERVER_ROOT, "dataset1", ['vector']),
        (HAPITEST20_SERVER_ROOT, "dataset1", ["scalar", "vector"]) ,
    )
    @unpack
    def test_info_with_parameters(self, root_url, dataset, parameters):
        hapi_provider = HapiProvider(root_url)
        data = hapi_provider.info(dataset, parameters)
        self.assertEqual(1+len(parameters), len(data['parameters']))

    @data (
        (HAPITEST33_SERVER_ROOT,),
        (HAPITEST20_SERVER_ROOT,)
    )
    @unpack
    def test_info_wrong_dataset(self, server_root):
        hapi_provider = HapiProvider(server_root)
        with self.assertRaises(HapiRequestError) as rc:
            hapi_provider.info('wrongdatasetname')
        self.assertEqual(1406, rc.exception.code)

    @data(
        (HAPITEST33_SERVER_ROOT, "dataset1"),
        (HAPITEST20_SERVER_ROOT, "dataset1"),
    )
    @unpack
    def test_info_wrong_parameters(self, server_root, dataset):
        hapi_provider = HapiProvider(server_root)
        with self.assertRaises(HapiRequestError) as rc:
            hapi_provider.info(dataset, ['wrongparam'])
        self.assertEqual(1407, rc.exception.code)


    @data(
            ('dataset1', '1970-01-02', '1970-01-01', [], 1404 ), # start time >= stop time
            ('dataset1', '1970-01-01', '1970-01-02', [], 1405 ), # times outside valid ranges
            ('wrong_dataset_name', '1970-01-01', '1970-01-02', [], 1406 ), # wrong dataset id
            ('dataset1', '1970-01-01', '1970-01-02', ['no_such_parameter'], 1407 ) # wrong dataset parameter id
    )
    @unpack
    def test_data_bad_request(self, dataset, start, stop, parameters, expected_err_code):
        hapi_provider = HapiProvider(HAPITEST33_SERVER_ROOT)
        with self.assertRaises(HapiRequestError) as rc:
             hapi_provider.data(dataset, start, stop, parameters)
        self.assertEqual(expected_err_code, rc.exception.code)

    def test_data_good_request(self):
        hapi_provider = HapiProvider(HAPITEST33_SERVER_ROOT)
        result = hapi_provider.data('dataset1', '1970-01-01Z', '1970-01-01T00:01:11Z', ['vector'])

        self.assertEqual(60, len(result['vector'].time))
        self.assertIsInstance(result['vector'], SpeasyVariable)
