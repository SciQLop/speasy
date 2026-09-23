#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import pickle
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pyzstd
from ddt import data, ddt
from numcodecs import Blosc

from speasy.core import epoch_to_datetime64
from speasy.core.dataprovider import DataProvider
from speasy.core.inventory.indexes import SpeasyIndex
from speasy.products.variable import DataContainer, SpeasyVariable, VariableAxis, VariableTimeAxis


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


def _server_blosc_arrays(obj):
    """Copy of speasy-proxy's encoder (speasy_proxy/api/compression.py), the reference for the wire format."""
    if isinstance(obj, dict):
        return {k: _server_blosc_arrays(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_server_blosc_arrays(v) for v in obj]
    if isinstance(obj, np.ndarray) and obj.dtype.kind in "biufcmM" and obj.nbytes > 0:
        raw = obj.view("i8") if obj.dtype.kind in "mM" else obj
        return {"__blosc__": Blosc(cname="zstd", clevel=1, shuffle=Blosc.SHUFFLE).encode(np.ascontiguousarray(raw)),
                "dtype": obj.dtype.str, "shape": obj.shape}
    return obj


def _time(n):
    return VariableTimeAxis(values=epoch_to_datetime64(np.arange(n, dtype=np.float64)))


def _var(values, extra_axes=()):
    return SpeasyVariable(axes=[_time(len(values)), *extra_axes],
                          values=DataContainer(values=values, is_time_dependent=True),
                          columns=[f"c{i}" for i in range(values.shape[1])] if values.ndim == 2 else ["Values"])


_VARIABLES = {
    "float64 1-D": _var(np.random.random(100)),
    "float32 3 columns": _var(np.random.random((100, 3)).astype(np.float32)),
    "int32": _var(np.arange(100, dtype=np.int32)),
    "spectrogram with time-dependent y": _var(
        np.random.random((50, 32)),
        [VariableAxis(name="y", values=np.random.random((50, 32)), is_time_dependent=True)]),
    "3-D values": _var(np.random.random((20, 8, 4)),
                       [VariableAxis(name="y", values=np.arange(8.)), VariableAxis(name="z", values=np.arange(4.))]),
    "string label axis": _var(np.random.random((10, 2)),
                              [VariableAxis(name="labels", values=np.array(["x", "y"]))]),
    "empty": _var(np.empty((0, 3))),
}


def _response(body: bytes, content_type: str):
    return SimpleNamespace(status_code=200, headers={"Content-Type": content_type}, bytes=body, url="fake")


def _proxy_get_data(response):
    from speasy.core.proxy import GetProduct
    with patch("speasy.core.proxy.http.get", return_value=response) as http_get:
        return GetProduct.get("amda/imf", "2020-01-01", "2020-01-02"), http_get.call_args.kwargs["params"]


def _assert_same_variable(test, expected, got):
    test.assertEqual(expected.to_dictionary().keys(), got.to_dictionary().keys())
    for exp_axis, got_axis in zip(expected.axes, got.axes):
        test.assertEqual(exp_axis.values.dtype, got_axis.values.dtype)
        np.testing.assert_array_equal(exp_axis.values, got_axis.values)
    test.assertEqual(expected.values.dtype, got.values.dtype)
    np.testing.assert_array_equal(expected.values, got.values)


@ddt
class ProxyBloscResponses(unittest.TestCase):
    def test_asks_for_blosc_when_a_decoder_is_available(self):
        _, params = _proxy_get_data(_response(pickle.dumps(None), "application/python-pickle"))
        self.assertEqual(params["compression"], "blosc")
        self.assertEqual(params["zstd_compression"], "true", "older servers still need to be asked for zstd")

    @data(*_VARIABLES)
    def test_blosc_response_round_trips(self, name):
        expected = _VARIABLES[name]
        body = pickle.dumps(_server_blosc_arrays(expected.to_dictionary()))
        got, _ = _proxy_get_data(_response(body, "application/x-speasy-blosc-pickle"))
        _assert_same_variable(self, expected, got)
        self.assertTrue(got.values.flags.writeable)

    def test_zstd_response_is_decoded(self):
        expected = _VARIABLES["float32 3 columns"]
        body = pyzstd.compress(pickle.dumps(expected.to_dictionary()))
        got, _ = _proxy_get_data(_response(body, "application/x-zstd-compressed"))
        _assert_same_variable(self, expected, got)

    def test_plain_pickle_response_is_not_zstd_decoded(self):
        """Decoding follows the response Content-Type, not what was asked: a server may ignore
        the compression parameters and answer with a plain pickle."""
        expected = _VARIABLES["float64 1-D"]
        got, _ = _proxy_get_data(_response(pickle.dumps(expected.to_dictionary()), "application/python-pickle"))
        _assert_same_variable(self, expected, got)

    def test_plain_pickle_inventory_is_not_zstd_decoded(self):
        from speasy.core.proxy import GetInventory
        inventory = SpeasyIndex(name="root", provider="mockprovider", uid="root")
        body = pickle.dumps(inventory.__dict__ | {"__spz_type__": "SpeasyIndex"})
        with patch("speasy.core.proxy.index.get", side_effect=lambda module, key, default=None: default), \
                patch("speasy.core.proxy.index.set"), \
                patch("speasy.core.proxy.inventory_from_dict", side_effect=lambda d, version: d) as from_dict, \
                patch("speasy.core.proxy.http.get", return_value=_response(body, "application/python-pickle")):
            GetInventory.get("mockprovider")
        self.assertEqual(from_dict.call_args.args[0], pickle.loads(body))
