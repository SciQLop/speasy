#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Offline tests for the `supermag` data provider inventory.

These tests never hit the network and never need a SuperMAG logon: the station
list endpoint is mocked with a small fixture, so the inventory can be checked
deterministically in CI.
"""

import inspect
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import speasy as spz
from speasy.config import supermag as supermag_cfg
from speasy.core.algorithms import fix_name
from speasy.core.impex.exceptions import MissingCredentials
from speasy.core.inventory.indexes import ParameterIndex
from speasy.data_providers import supermag as supermag_module
from speasy.data_providers.supermag import SuperMAGWebservice, _records_to_variable
from speasy.inventories import tree

# Small station-list fixture, same shape as the JHUAPL endpoint response.
# "9XY" there for fix_name() test
_STATIONS_FIXTURE = [
    {"id": "YKC", "geolon": 245.52, "geolat": 62.48, "name": "Yellowknife",
     "operator": ["CANMOS", "INTERMAGNET", "THEMIS"]},
    {"id": "ABK", "geolon": 18.82, "geolat": 68.36, "name": "Abisko",
     "operator": ["INTERMAGNET"]},
    {"id": "9XY", "geolon": 1.0, "geolat": 2.0, "name": "Synthetic", "operator": []},
]


def _build_provider(stations):
    """Instantiate the provider with a mocked station list."""
    with patch.object(SuperMAGWebservice, "_get_stations", lambda self: stations):
        return SuperMAGWebservice()


class SuperMAGInventoryTest(unittest.TestCase):

    def test_stations_inventory_without_network(self):
        ws = _build_provider(_STATIONS_FIXTURE)
        params = ws.flat_inventory.parameters
        self.assertEqual(len(params), len(_STATIONS_FIXTURE))
        self.assertIn("Stations/YKC", params)
        self.assertIn("Stations/ABK", params)

    def test_station_node_metadata(self):
        ws = _build_provider(_STATIONS_FIXTURE)
        node = ws.flat_inventory.parameters["Stations/YKC"]
        self.assertIsInstance(node, ParameterIndex)
        self.assertEqual(node.spz_provider(), "supermag")
        self.assertEqual(node.spz_uid(), "Stations/YKC")
        self.assertEqual(node.station, "YKC")
        self.assertEqual(node.label, "Yellowknife")
        self.assertEqual(node.geolat, 62.48)
        self.assertEqual(node.geolon, 245.52)
        self.assertEqual(node.operator, ["CANMOS", "INTERMAGNET", "THEMIS"])

    def test_sanitised_node_name(self):
        """ node name sanitised but uid keeps IAGA code 
          The tree attribute key is a valid Python identifier
          while the uid  keeps the raw IAGA code.
        """
        _build_provider(_STATIONS_FIXTURE)
        stations_node = tree.supermag.Stations
        self.assertIn(fix_name("9XY"), stations_node.__dict__)
        self.assertEqual(stations_node.__dict__[fix_name("9XY")].spz_uid(), "Stations/9XY")

    def test_empty_station_list_does_not_crash(self):
        ws = _build_provider([])
        self.assertEqual(ws.flat_inventory.parameters, {})
        # The Stations container node is still present, just empty.
        self.assertTrue(hasattr(tree.supermag, "Stations"))


class _LiveSuperMAGMixin:
    """Build the provider against the live endpoint, skipping on a transient glitch.

    Instantiating SuperMAGWebservice runs build_inventory -> _get_stations, which
    intermittently answers HTTP 200 with a non-JSON PHP error body. In that case we
    skip (never fail) so a server-side glitch can't block a push or CI run.
    """

    def _build_or_skip(self):
        try:
            return SuperMAGWebservice()  # __init__ -> build_inventory -> _get_stations
        except Exception as e:  # e.g. JSONDecodeError when SuperMAG returns an error page
            self.skipTest(f"SuperMAG station endpoint unavailable ({e!r})")


@unittest.skipIf(spz.config.core.disabled_providers.get().intersection({'supermag', 'SuperMAG'}),
                 "supermag provider not available")
class SuperMAGNetworkTest(_LiveSuperMAGMixin, unittest.TestCase):
    """Live tests hitting the real JHUAPL public stations endpoint
    (doesnt require a logon) 

    Skipped  when SuperMAG is unreachable or returns a non-JSON error:
    the request intermittently fails ( HTTP 200 with a PHP error body)
    """

    def test_get_real_station_list(self):
        stations = self._build_or_skip()._get_stations()
        if not stations:
            self.skipTest("SuperMAG station endpoint returned no data")
        self.assertIsInstance(stations, list)
        self.assertGreater(len(stations), 100)
        first = stations[0]
        for key in ("id", "geolat", "geolon"):
            self.assertIn(key, first)

    def test_real_inventory_populated(self):
        ws = self._build_or_skip()
        if not ws.flat_inventory.parameters:
            self.skipTest("SuperMAG station endpoint returned no data")
        self.assertGreater(len(ws.flat_inventory.parameters), 100)


# Small data-api fixture: two records at 2015-03-17T00:00 and 00:01 UTC. The E
# component of the second record is the SuperMAG NaN value (999999).
_RECORDS_FIXTURE = [
    {"tval": 1426550400.0,
     "N": {"nez": 1.0, "geo": 10.0}, "E": {"nez": 2.0, "geo": 20.0}, "Z": {"nez": 3.0, "geo": 30.0}},
    {"tval": 1426550460.0,
     "N": {"nez": 4.0, "geo": 40.0}, "E": {"nez": 999999, "geo": 999999}, "Z": {"nez": 6.0, "geo": 60.0}},
]


class SuperMAGRecordsTest(unittest.TestCase):
    """Offline tests for _records_to_variable"""

    def test_time_axis_and_columns(self):
        var = _records_to_variable(_RECORDS_FIXTURE, "nez", "ABK")
        self.assertEqual(var.columns, ["N", "E", "Z"])
        self.assertEqual(var.values.shape, (2, 3))
        self.assertEqual(var.time[0], np.datetime64("2015-03-17T00:00:00", "ns"))
        self.assertEqual(var.time[1], np.datetime64("2015-03-17T00:01:00", "ns"))

    def test_nez_and_geo_not_equal(self):
        nez = _records_to_variable(_RECORDS_FIXTURE, "nez", "ABK")
        geo = _records_to_variable(_RECORDS_FIXTURE, "geo", "ABK")
        self.assertEqual(nez.values[0].tolist(), [1.0, 2.0, 3.0])
        self.assertEqual(geo.values[0].tolist(), [10.0, 20.0, 30.0])

    def test_supermag_nan_becomes_nan(self):
        var = _records_to_variable(_RECORDS_FIXTURE, "nez", "ABK")
        self.assertTrue(np.isnan(var.values[1, 1]))   # E of the second record was 999999
        self.assertEqual(var.values[1, 0], 4.0)        # neighbours untouched
        self.assertEqual(var.values[1, 2], 6.0)

    def test_meta_has_frame_and_station(self):
        var = _records_to_variable(_RECORDS_FIXTURE, "geo", "ABK")
        self.assertEqual(var.meta["UNITS"], "nT")
        self.assertEqual(var.meta["COORDINATE_SYSTEM"], "geo")
        self.assertEqual(var.meta["station"], "ABK")

    def test_empty_records_returns_none(self):
        self.assertIsNone(_records_to_variable([], "nez", "ABK"))


class SuperMAGLogonConfigTest(unittest.TestCase):
    """The logon comes from config.supermag.logon() (env var or config.ini), not os.environ."""

    def test_logon_from_env_var(self):
        with patch.dict(os.environ, {"SPEASY_SUPERMAG_LOGON": "testid"}):
            self.assertEqual(supermag_cfg.logon(), "testid")

    def test_no_logon_raises_missing_credentials(self):
        ws = _build_provider([])  # offline provider (mocked station list)
        start = datetime(2015, 3, 17, 0, 0, tzinfo=timezone.utc)
        stop = datetime(2015, 3, 17, 1, 0, tzinfo=timezone.utc)
        # Empty env var forces an empty logon deterministically (config.ini is not consulted).
        with patch.dict(os.environ, {"SPEASY_SUPERMAG_LOGON": ""}):
            with self.assertRaises(MissingCredentials):
                ws.get_data("Stations/ABK", start, stop, disable_cache=True)

    def test_provider_does_not_read_os_environ_directly(self):
        self.assertNotIn("os.environ", inspect.getsource(supermag_module))


@unittest.skipUnless(os.environ.get("SPEASY_SUPERMAG_LOGON"),
                     "SPEASY_SUPERMAG_LOGON not set (gated integration test)")
@unittest.skipIf(spz.config.core.disabled_providers.get().intersection({'supermag', 'SuperMAG'}),
                 "supermag provider not available")
class SuperMAGGetDataIntegrationTest(_LiveSuperMAGMixin, unittest.TestCase):
    """Gated end-to-end test: real logon + real data-api.php call.

    Skipped  when SuperMAG is unreachable or returns a non-JSON error:
    the request intermittently fails ( HTTP 200 with a PHP error body)

    """

    def test_get_data_returns_non_empty_variable(self):
        ws = self._build_or_skip()
        start = datetime(2015, 3, 17, 0, 0, tzinfo=timezone.utc)
        stop = datetime(2015, 3, 17, 1, 0, tzinfo=timezone.utc)
        try:
            var = ws.get_data("Stations/ABK", start, stop, disable_cache=True)
        except Exception as e:
            self.skipTest(f"SuperMAG data-api unavailable ({e!r})")
        if var is None:
            self.skipTest("SuperMAG data-api returned no data for the test window")
        self.assertGreater(len(var), 0)
        self.assertEqual(var.columns, ["N", "E", "Z"])
        self.assertEqual(var.values.shape[1], 3)


if __name__ == "__main__":
    unittest.main()
