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


class GetInventoryConditionalRequest(unittest.TestCase):
    def test_if_modified_since_header_is_a_valid_http_date(self):
        """The same RFC 7231 bug was fixed in three places; only cda had a test.

        ``datetime.ctime()`` produces "Thu Jan  1 00:00:00 2026", which is not a
        valid HTTP-date, and some servers answer 400 to it.
        """
        from speasy.core.proxy import GetInventory

        saved_inventory = SpeasyIndex(name="root", provider="mockprovider", uid="root")
        saved_inventory.build_date = "2026-01-01T00:00:00+00:00"

        def fake_index_get(module, key, default=None):
            if module == "proxy_inventories":
                return saved_inventory
            if module == "proxy_inventories_save_date":
                return datetime(2000, 1, 1, tzinfo=timezone.utc)  # stale, must revalidate
            return default

        with patch("speasy.core.proxy.index.get", side_effect=fake_index_get), \
                patch("speasy.core.proxy.http.get",
                      side_effect=RuntimeError("stop after headers are built")) as http_get:
            with self.assertRaises(RuntimeError):
                GetInventory.get("mockprovider")

        self.assertEqual(http_get.call_args.kwargs["headers"]["If-Modified-Since"],
                         "Thu, 01 Jan 2026 00:00:00 GMT")
