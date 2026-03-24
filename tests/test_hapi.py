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

    def test_capabilities_returns_dict(self):
        hapi_provider = HapiProvider(CDAWEB_SERVER_ROOT)
        result = hapi_provider.capabilities()
        from pprint import pprint
        self.assertEqual( result["HAPI"], "2.0")
        self.assertCountEqual( result["outputFormats"], ['json', 'csv', 'binary'])

    def test_about_returns_dict(self):
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
    def test_hapi_returns_html(self, root_url, contents):
        hapi_provider = HapiProvider(root_url)
        html_hapi = hapi_provider.hapi()
        self.assertIn("<html", html_hapi.lower())
        for c in contents:
            self.assertIn(c, html_hapi)

    def test_catalog_returns_dict(self): ...
    def test_info_returns_dict(self): ...

    def test_data_returns_speasy_variable(self): ...

    def test_data_raises_hapi_no_data_on_1201(self): ...
    def test_data_raises_hapi_request_error_on_unknown_dataset(self): ...
    def test_data_raises_hapi_request_error_on_bad_time_format(self): ...
    def test_data_raises_hapi_server_error_on_1500(self): ...
