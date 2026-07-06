#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Offline tests for the `supermag` data provider inventory.

These tests never hit the network and never need a SuperMAG logon: the station
list endpoint is mocked with a small fixture, so the inventory can be checked
deterministically in CI.
"""

import unittest
from unittest.mock import patch

import numpy as np
import speasy as spz
from speasy.core.algorithms import fix_name
from speasy.core.inventory.indexes import ParameterIndex
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
    """Instantiate the provider with a mocked (offline) station list."""
    with patch.object(SuperMAGWebservice, "_get_stations", lambda self: stations):
        return SuperMAGWebservice()


class SuperMAGInventoryTest(unittest.TestCase):

    def test_builds_stations_inventory_without_network_or_logon(self):
        ws = _build_provider(_STATIONS_FIXTURE)
        params = ws.flat_inventory.parameters
        self.assertEqual(len(params), len(_STATIONS_FIXTURE))
        self.assertIn("Stations/YKC", params)
        self.assertIn("Stations/ABK", params)

    def test_station_node_carries_expected_metadata(self):
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

    def test_node_name_is_sanitised_but_uid_keeps_raw_iaga(self):
        _build_provider(_STATIONS_FIXTURE)  # rebuilds tree.supermag from the fixture
        stations_node = tree.supermag.Stations
        # The tree attribute key is a valid Python identifier ...
        self.assertIn(fix_name("9XY"), stations_node.__dict__)
        # ... while the uid (used to call the API) keeps the raw IAGA code.
        self.assertEqual(stations_node.__dict__[fix_name("9XY")].spz_uid(), "Stations/9XY")

    def test_empty_station_list_does_not_crash(self):
        ws = _build_provider([])
        self.assertEqual(ws.flat_inventory.parameters, {})
        # The Stations container node is still present, just empty.
        self.assertTrue(hasattr(tree.supermag, "Stations"))


@unittest.skipIf(spz.config.core.disabled_providers.get().intersection({'supermag', 'SuperMAG'}),
                 "supermag provider not available")
class SuperMAGNetworkTest(unittest.TestCase):
    """Live tests hitting the real JHUAPL public stations endpoint (no logon)."""

    def test_get_stations_returns_real_station_list(self):
        stations = SuperMAGWebservice()._get_stations()
        self.assertIsInstance(stations, list)
        self.assertGreater(len(stations), 100)  # SuperMAG has ~600 stations
        first = stations[0]
        for key in ("id", "geolat", "geolon"):
            self.assertIn(key, first)

    def test_real_inventory_is_populated(self):
        ws = SuperMAGWebservice()  # __init__ -> build_inventory -> _get_stations
        self.assertGreater(len(ws.flat_inventory.parameters), 100)


# Small data-api fixture: two records at 2015-03-17T00:00 and 00:01 UTC. The E
# component of the second record is the SuperMAG gap sentinel (999999).
_RECORDS_FIXTURE = [
    {"tval": 1426550400.0,
     "N": {"nez": 1.0, "geo": 10.0}, "E": {"nez": 2.0, "geo": 20.0}, "Z": {"nez": 3.0, "geo": 30.0}},
    {"tval": 1426550460.0,
     "N": {"nez": 4.0, "geo": 40.0}, "E": {"nez": 999999, "geo": 999999}, "Z": {"nez": 6.0, "geo": 60.0}},
]


class SuperMAGRecordsTest(unittest.TestCase):
    """Offline mapping tests for _records_to_variable (no network, no logon)."""

    def test_time_axis_and_columns(self):
        var = _records_to_variable(_RECORDS_FIXTURE, "nez", "ABK")
        self.assertEqual(var.columns, ["N", "E", "Z"])
        self.assertEqual(var.values.shape, (2, 3))
        self.assertEqual(var.time[0], np.datetime64("2015-03-17T00:00:00", "ns"))
        self.assertEqual(var.time[1], np.datetime64("2015-03-17T00:01:00", "ns"))

    def test_nez_and_geo_select_different_values(self):
        nez = _records_to_variable(_RECORDS_FIXTURE, "nez", "ABK")
        geo = _records_to_variable(_RECORDS_FIXTURE, "geo", "ABK")
        self.assertEqual(nez.values[0].tolist(), [1.0, 2.0, 3.0])
        self.assertEqual(geo.values[0].tolist(), [10.0, 20.0, 30.0])

    def test_gap_sentinel_becomes_nan(self):
        var = _records_to_variable(_RECORDS_FIXTURE, "nez", "ABK")
        self.assertTrue(np.isnan(var.values[1, 1]))   # E of the second record was 999999
        self.assertEqual(var.values[1, 0], 4.0)        # neighbours untouched
        self.assertEqual(var.values[1, 2], 6.0)

    def test_meta_carries_units_frame_and_station(self):
        var = _records_to_variable(_RECORDS_FIXTURE, "geo", "ABK")
        self.assertEqual(var.meta["UNITS"], "nT")
        self.assertEqual(var.meta["COORDINATE_SYSTEM"], "geo")
        self.assertEqual(var.meta["station"], "ABK")

    def test_empty_records_returns_none(self):
        self.assertIsNone(_records_to_variable([], "nez", "ABK"))


if __name__ == "__main__":
    unittest.main()
