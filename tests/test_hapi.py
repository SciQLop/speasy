import unittest
from ddt import data, ddt, unpack

from speasy.core.hapi.client import HapiClient, HapiEndpoint
from speasy.core.hapi.provider import HapiProvider
from speasy.core.hapi.exceptions import HapiRequestError, HapiServerError, HapiNoData


AMDA_SERVER_ROOT = "https://amda.irap.omp.eu/service"
HAPITEST33_SERVER_ROOT = "https://hapi-server.org/servers/TestData3.3"
CDAWEB_SERVER_ROOT = "https://cdaweb.gsfc.nasa.gov"

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


@ddt
class TestHapiProvider(unittest.TestCase):

    def test_capabilities(self):
        hapi_provider = HapiProvider(CDAWEB_SERVER_ROOT)
        result = hapi_provider.capabilities()
        from pprint import pprint
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
    def test_info(self, root_url, dataset, paramlist_len):
        # will 
        hapi_provider = HapiProvider(root_url)
        data = hapi_provider.info(dataset)
        self.assertIn("HAPI", data)
        self.assertIn("parameters", data)
        self.assertEqual(len(data['parameters']), paramlist_len)

    def test_data_raises_hapi_no_data_on_1201(self): ...
    def test_data_raises_hapi_request_error_on_unknown_dataset(self): ...
    def test_data_raises_hapi_request_error_on_bad_time_format(self): ...
    def test_data_raises_hapi_server_error_on_1500(self): ...
