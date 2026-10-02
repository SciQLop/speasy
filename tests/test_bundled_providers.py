import os
import unittest
from unittest.mock import patch

from speasy.core.dataprovider import main_provider_name, registered_providers
from speasy.core.requests_scheduling import request_dispatch as rd
from speasy.data_providers import CsaWebservice


class BundledProviders(unittest.TestCase):
    def test_bundled_providers_register_in_the_historical_init_order(self):
        self.assertEqual(list(registered_providers()),
                         ["amda", "csa", "cda", "ssc", "archive", "uiowaephtool", "cdpp3dview"])

    def test_aliases_resolve_to_their_main_name(self):
        expected = {"cdaweb": "cda", "sscweb": "ssc", "generic_archive": "archive", "file": "archive",
                    "UiowaEphTool": "uiowaephtool", "3DView": "cdpp3dview"}
        self.assertEqual({alias: main_provider_name(alias) for alias in expected}, expected)

    def test_started_providers_use_their_declared_name(self):
        for main_name, cls in registered_providers().items():
            instance = rd.PROVIDERS.get(main_name)
            if instance is not None:
                with self.subTest(main_name):
                    self.assertIsInstance(instance, cls)
                    self.assertEqual(instance.provider_name, cls.NAME)


class CsaServerCheck(unittest.TestCase):
    def test_csa_reports_down_behind_an_http_proxy(self):
        with patch.dict(os.environ, {"HTTP_PROXY": "http://proxy.example:3128"}), \
                patch("speasy.data_providers.csa.is_server_up") as check, \
                self.assertLogs("speasy.data_providers.csa", "WARNING"):
            self.assertFalse(rd._is_server_up(CsaWebservice))
        check.assert_not_called()

    def test_csa_checks_its_url_without_a_proxy(self):
        with patch.dict(os.environ), patch("speasy.data_providers.csa.is_server_up", return_value=True) as check:
            os.environ.pop("HTTP_PROXY", None)
            self.assertTrue(rd._is_server_up(CsaWebservice))
        check.assert_called_once_with(url=CsaWebservice.BASE_URL)


if __name__ == "__main__":
    unittest.main()
