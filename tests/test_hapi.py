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

    def test_build_url_info_with_dataset(self): ...
    def test_build_url_data_with_params(self): ...

    def test_get_info_returns_json(self): ...
    # mock requests.get → 200 + json valide

    def test_raises_on_http_error(self): ...
    # mock requests.get → 500

    def test_check_status_raises_hapi_request_error_on_1401(self): ...
    def test_check_status_raises_hapi_server_error_on_1500(self): ...
    def test_check_status_raises_hapi_no_data_on_1201(self): ...
    def test_check_status_does_not_raise_on_1200(self): ...

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
    
    
    def test_data_raises_hapi_no_data_on_1201(self): ...
    def test_data_raises_hapi_request_error_on_unknown_dataset(self): ...
    def test_data_raises_hapi_request_error_on_bad_time_format(self): ...
    def test_data_raises_hapi_server_error_on_1500(self): ...
