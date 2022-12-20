#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `cdpp_3dview` package."""
import os
import unittest
from datetime import datetime, timedelta, timezone

from ddt import data, ddt, unpack

import speasy as spz
from speasy.inventories import flat_inventories
from speasy.webservices.cdpp_3dview.ws import _WS_impl

_ws = _WS_impl()


@ddt
class CDPP_3DViewModule(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data((_ws.get_satellite_list(), 0),
          (_ws.get_spacecraft_list(), 163),
          (_ws.get_planet_list(), 35),
          (_ws.get_comet_list(), 3),
          (_ws.get_asteroid_list(), 2))
    @unpack
    def test_can_list_bodies(self, bodies, min_expected_size):
        self.assertGreaterEqual(len(bodies), min_expected_size)

    def test_can_list_frames(self):
        self.assertGreaterEqual(len(_ws.get_frame_list()), 76)

    def test_can_get_trajectory(self):
        traj = _ws.get_orbit_data(body=_ws.get_spacecraft_list()[0],
                                  start_time=datetime(2010, 1, 1, tzinfo=timezone.utc),
                                  stop_time=datetime(2010, 1, 2, tzinfo=timezone.utc))
        self.assertIsNotNone(traj)
        self.assertGreater(len(traj), timedelta(days=1).total_seconds() / (5 * 60))
