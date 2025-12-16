#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import unittest
from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import SpeasyIndex


class SpeasyProxy(unittest.TestCase):
    class MockProvider(DataProvider):
        def __init__(self):
            super().__init__("mockprovider")

        def build_inventory(self, root: SpeasyIndex) -> SpeasyIndex:
            return root

        def __del__(self):
            from speasy.core.dataprovider import PROVIDERS
            if "mockprovider" in PROVIDERS:
                del (PROVIDERS["mockprovider"])

    def tearDown(self):
        from speasy.core.dataprovider import PROVIDERS
        if "mockprovider" in PROVIDERS:
            del (PROVIDERS["mockprovider"])

    def test_should_not_crash_if_provider_disabled_on_proxy(self):
        """This test emulate what we get when a provider is disabled on the proxy server.

        In this case, when asking for the inventory through the proxy given provider name, the proxy
        will return a 400 error. We want to make sure that the DataProvider class can handle this case
        gracefully and still be instantiated.
        """
        mock_provider = SpeasyProxy.MockProvider()
        self.assertIsNotNone(mock_provider)
