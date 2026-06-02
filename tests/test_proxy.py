#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

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


class GetInventoryCacheDesync(unittest.TestCase):
    def test_missing_inventory_with_fresh_date_must_refetch(self):
        """Regression for the sciqlop-cache migration crash.

        After migrating to sciqlop-cache, the pickled inventory object can fail
        to deserialize and gets dropped (``index.get`` -> ``None``) while the
        sibling ``proxy_inventories_save_date`` entry (a plain ``datetime``)
        survives and is still fresh. ``GetInventory.get`` must not trust the
        date alone and return a ``None`` inventory -- it must fall through and
        re-fetch from the proxy. Returning ``None`` here ultimately raises
        ``AttributeError: 'NoneType' object has no attribute '__dict__'`` in
        ``inventory_has_changed`` and disables every proxied provider.
        """
        from speasy.core.proxy import GetInventory

        def fake_index_get(module, key, default=None):
            if module == "proxy_inventories":
                return None  # dropped: failed to load after migration
            if module == "proxy_inventories_save_date":
                return datetime.now(tz=timezone.utc)  # still fresh
            return default

        with patch("speasy.core.proxy.index.get", side_effect=fake_index_get), \
                patch("speasy.core.proxy.http.get",
                      side_effect=RuntimeError("fetch attempted")) as http_get:
            with self.assertRaises(RuntimeError):
                GetInventory.get("mockprovider")
        self.assertTrue(http_get.called,
                        "GetInventory.get returned the dropped (None) inventory "
                        "instead of re-fetching from the proxy")
