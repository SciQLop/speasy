#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `cdpp3dview` package."""
import unittest
from datetime import datetime, timezone

from ddt import data, ddt

import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex
from speasy.data_providers import cdpp3dview

GEOTAIL_SAMPLINGS = [
    {
        "product": "GEOTAIL",
        "start_time": datetime(1992, 7, 30, 1, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1992, 7, 30, 2, 0, 0, tzinfo=timezone.utc),
        "sampling": "60",
    },
    {
        "product": "GEOTAIL",
        "start_time": datetime(1992, 7, 30, 1, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1992, 7, 30, 2, 0, 0, tzinfo=timezone.utc),
        "sampling": "600",
    },
]

GEOTAIL_FRAMES = [
    {
        "product": "GEOTAIL",
        "start_time": datetime(1992, 7, 30, 1, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1992, 7, 30, 2, 0, 0, tzinfo=timezone.utc),
        "coordinate_frame": f,
    } for f in ["J2000", "ECLIPJ2000", "HEE", "HEEQ", "HCI", "IAU_SUN", "GSE", "GSM", "SM", "IAU_EARTH", ]
]


SOME_PRODUCTS = [
    {
        "product": "GEOTAIL",
        "start_time": datetime(1992, 7, 30, 1, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1992, 7, 30, 2, 0, 0, tzinfo=timezone.utc)
    },
    {
        "product": "WIND",
        "start_time": datetime(1994, 11, 17, 0, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1994, 11, 18, 0, 12, 0, tzinfo=timezone.utc),
    },
    {
        "product": "SOHO",
        "start_time": datetime(1995, 12, 3, 0, 12, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1995, 12, 4, 0, 0, 30, tzinfo=timezone.utc),
    },
    {
        "product": "Pioneer10",
        "start_time": datetime(1972, 3, 5, 12, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1972, 3, 6, 0, 0, 0, tzinfo=timezone.utc),
    },
    {
        "product": "Pioneer11",
        "start_time": datetime(1973, 4, 8, 12, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1973, 4, 9, 0, 0, 0, tzinfo=timezone.utc),
    },
    {
        "product": "Voyager_1",
        "start_time": datetime(1977, 9, 5, 13, 59, 25, tzinfo=timezone.utc),
        "stop_time": datetime(1977, 9, 6, 0, 0, 0, tzinfo=timezone.utc),
    },
    {
        "product": "Galileo",
        "start_time": datetime(1989, 10, 19, 1, 29, 33, tzinfo=timezone.utc),
        "stop_time": datetime(1989, 11, 22, 4, 34, 38, tzinfo=timezone.utc),
    },
    {
        "product": "Cassini",
        "start_time": datetime(1997, 10, 15, 10, 0, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1997, 11, 16, 10, 30, 0, tzinfo=timezone.utc),
    },
    {
        "product": "ACE",
        "start_time": datetime(1997, 8, 26, 17, 48, 0, tzinfo=timezone.utc),
        "stop_time": datetime(1997, 8, 27, 17, 49, 0, tzinfo=timezone.utc),
    },
    {
        "product": "CLUSTER1",
        "start_time": datetime(2000, 8, 22, 0, 18, 30, tzinfo=timezone.utc),
        "stop_time": datetime(2000, 8, 23, 0, 0, 30, tzinfo=timezone.utc),
    },

]


@ddt
class Cdpp3dViewTest(unittest.TestCase):
    def setUp(self):
        self.cdpp3d = cdpp3dview.Cdpp3dViewWebservice()

    def tearDown(self):
        pass

    @data(*SOME_PRODUCTS)
    def test_get_data_on_products(self, kw):
        result = self.cdpp3d.get_data(**kw,
                                      disable_cache=True,
                                      disable_proxy=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    @data(*GEOTAIL_FRAMES)
    def test_get_data_on_frames(self, kw):
        result = self.cdpp3d.get_data(**kw,
                                      disable_cache=True,
                                      disable_proxy=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    @data(*GEOTAIL_SAMPLINGS)
    def test_get_data_on_samplings(self, kw):
        result = self.cdpp3d.get_data(**kw,
                                      disable_cache=True,
                                      disable_proxy=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

        interval_secs = int(kw["sampling"])

        # make sure sampling is respected
        for i in range(len(result.time) - 1):
            t1 = result.time[i]
            t2 = result.time[i + 1]
            self.assertGreaterEqual(t2 - t1, interval_secs)

    def test_inventory_exists(self):
        self.assertIsInstance(
            spz.inventories.tree.cdpp3dview.Trajectories, SpeasyIndex)
        self.assertIsInstance(
            spz.inventories.tree.cdpp3dview.Trajectories.ASTEROID, SpeasyIndex)
        self.assertIsInstance(
            spz.inventories.tree.cdpp3dview.Trajectories.SPACECRAFT, SpeasyIndex)
        self.assertIsInstance(
            spz.inventories.tree.cdpp3dview.Trajectories.PLANET, SpeasyIndex)
        self.assertIsInstance(
            spz.inventories.tree.cdpp3dview.Trajectories.ASTEROID.Dimorphos, ParameterIndex)

    def test_get_frames(self):
        frames = self.cdpp3d.get_frames()
        self.assertGreater(len(frames), 0)
        self.assertIn('J2000', frames)
        self.assertIn('GSE', frames)

    def test_get_bodies(self):
        bodies = self.cdpp3d._get_bodies()
        self.assertGreater(len(bodies), 0)
        bodies_names = [b['name'] for b in bodies]
        self.assertIn('GEOTAIL', bodies_names)
        self.assertIn('MEX', bodies_names)

    def test_parameter_range(self):
        param_range = self.cdpp3d.parameter_range('GEOTAIL')
        self.assertIsNotNone(param_range)
        self.assertIsInstance(param_range[0], datetime)
        self.assertIsInstance(param_range[1], datetime)
        self.assertLess(param_range[0], param_range[1])


@ddt
class Cdpp3dViewTestErrorsCaught(unittest.TestCase):
    def setUp(self):
        self.cdpp3d = cdpp3dview.Cdpp3dViewWebservice()

    def tearDown(self):
        pass

    @data(
        {
            "product": "GEOTAIL",
            "start_time": datetime(1992, 7, 30, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(1992, 7, 30, 2, 0, 0, tzinfo=timezone.utc),
            "coordinate_frame": 'J2000',
            "sampling": "60",
        }
    )
    def test_get_data_wrong_kwarg(self, kw):
        with self.assertRaises(TypeError):
            self.cdpp3d.get_data(**kw,
                                 wrong_arg=True,
                                 )

    @data(
        {
            "product": "GEOTAIL",
            "start_time": datetime(1992, 7, 30, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(1992, 7, 30, 2, 0, 0, tzinfo=timezone.utc),
            "coordinate_frame": 'WRONG_FRAME',
            "sampling": "60",
        }
    )
    def test_get_data_wrong_frame(self, kw):
        with self.assertRaises(cdpp3dview.Cdpp3dViewWebException):
            self.cdpp3d.get_data(**kw,
                                 disable_cache=True,
                                 disable_proxy=True
                                 )

    @data(
        {
            "product": "GEOTAIL",
            "start_time": datetime(1800, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(1800, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            "coordinate_frame": 'J2000',
            "sampling": "60",
        }
    )
    def test_get_data_off_range(self, kw):

        with self.assertLogs(level="WARNING") as cm:
            data = self.cdpp3d.get_data(**kw,
                                        disable_cache=True,
                                        disable_proxy=True
                                        )
        self.assertIsNone(data)
        self.assertIn(
            f"You are requesting GEOTAIL outside of its definition range", cm.output[0])


if __name__ == '__main__':
    unittest.main()
