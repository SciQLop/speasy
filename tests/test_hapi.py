import unittest
from ddt import data, ddt, unpack

from speasy.core.hapi.client import HapiClient, HapiEndpoint
from speasy.core.hapi.provider import HapiProvider
from speasy.core.hapi.exceptions import HapiRequestError, HapiServerError, HapiNoData
from speasy.products.variable import SpeasyVariable


AMDA_SERVER_ROOT = "https://amda.irap.omp.eu/service"
HAPITEST33_SERVER_ROOT = "https://hapi-server.org/servers/TestData3.3"
CDAWEB_SERVER_ROOT = "https://cdaweb.gsfc.nasa.gov"

@ddt
class TestHapiClient(unittest.TestCase):

    def test_build_url(self):
        hapi_client = HapiClient(AMDA_SERVER_ROOT)
        amda_about_url = hapi_client._build_url(endpoint=HapiEndpoint.ABOUT)
        self.assertEqual(f"{AMDA_SERVER_ROOT}/hapi/about", amda_about_url)

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


@ddt
class TestHapiProvider(unittest.TestCase):

    def test_capabilities(self):
        hapi_provider = HapiProvider(CDAWEB_SERVER_ROOT)
        result = hapi_provider.capabilities()
        self.assertEqual( result["HAPI"], "2.0")
        self.assertCountEqual( result["outputFormats"], ['json', 'csv', 'binary'])

    def test_about(self):
        hapi_provider = HapiProvider(HAPITEST33_SERVER_ROOT)
        result = hapi_provider.about()
        self.assertEqual(result["HAPI"], "3.3")
        self.assertEqual( result["status"]["code"], 1200)
        self.assertIsInstance(result["note"], list)

    @data (
        (HAPITEST33_SERVER_ROOT, ["data", "info"]),
        (AMDA_SERVER_ROOT, ["data", "info"]),
        (CDAWEB_SERVER_ROOT, ["data", "info"]),
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
        (AMDA_SERVER_ROOT,),
        (CDAWEB_SERVER_ROOT,)
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
        self.assertEqual(data["status"]["code"], 1200)
        self.assertEqual(data["status"]["message"].lower(), "ok")

    @data(
        (HAPITEST33_SERVER_ROOT,"dataset1", 2),
        (CDAWEB_SERVER_ROOT, "AC_OR_SSC", 6),
    )
    @unpack
    def test_info_dataset_only(self, root_url, dataset, nb_params):
        hapi_provider = HapiProvider(root_url)
        data = hapi_provider.info(dataset)
        self.assertIn("HAPI", data)
        self.assertIn("parameters", data)
        self.assertEqual(len(data['parameters']), nb_params)

    @data(
        (HAPITEST33_SERVER_ROOT, "dataset1", ['vector']),
        (CDAWEB_SERVER_ROOT, "AC_OR_SSC", ["GSE_LAT", "GSE_LON"]) ,
    )
    @unpack
    def test_info_with_parameters(self, root_url, dataset, parameters):
        hapi_provider = HapiProvider(root_url)
        data = hapi_provider.info(dataset, parameters)
        self.assertEqual(len(data['parameters']), 1+len(parameters))

    @data (
        (HAPITEST33_SERVER_ROOT,),
        (AMDA_SERVER_ROOT,),
        (CDAWEB_SERVER_ROOT,)
    )
    @unpack
    def test_info_wrong_dataset(self, server_root):
        hapi_provider = HapiProvider(server_root)
        err_response = hapi_provider.info('wrongdataset')
        self.assertIn("error", err_response)
        self.assertIn("code", err_response)
        self.assertIn("message", err_response)
        self.assertEqual(err_response["error"], "request")
        self.assertEqual(1406, err_response["code"])

    @data(
        (HAPITEST33_SERVER_ROOT, "dataset1"),
        (CDAWEB_SERVER_ROOT, "AC_OR_SSC"),
        # (AMDA_SERVER_ROOT, "ace-epam-ca60") should return 1407 not 1401
    )
    @unpack
    def test_info_wrong_parameters(self, server_root, dataset):
        hapi_provider = HapiProvider(server_root)
        err_response = hapi_provider.info(dataset, ['wrongparam'])
        self.assertIn("message", err_response)
        self.assertEqual("request", err_response["error"])
        self.assertEqual(1407, err_response["code"])


    @data(
            ('dataset1', '1970-01-02', '1970-01-01', [], 1404 ), # start time >= stop time
            ('dataset1', '1970-01-01', '1970-01-02', [], 1405 ), # times outside valid ranges
            ('wrong_dataset_name', '1970-01-01', '1970-01-02', [], 1406 ), # wrong dataset id
            ('dataset1', '1970-01-01', '1970-01-02', ['no_such_parameter'], 1407 ) # wrong dataset parameter id
    )
    @unpack
    def test_data_bad_request(self, dataset, start, stop, parameters, expected_err_code):
        hapi_provider = HapiProvider(HAPITEST33_SERVER_ROOT)
        err_response = hapi_provider.data(dataset, start, stop, parameters)
        self.assertIn("message", err_response)
        self.assertEqual("request", err_response["error"])
        self.assertEqual(expected_err_code, err_response["code"])

    def test_data_good_request(self):
        hapi_provider = HapiProvider(HAPITEST33_SERVER_ROOT)
        result = hapi_provider.data('dataset1', '1970-01-01Z', '1970-01-01T00:01:11Z', ['vector'])

        self.assertEqual(60, len(result['vector'].time))
        self.assertIsInstance(result['vector'], SpeasyVariable)
