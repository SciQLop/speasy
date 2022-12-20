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

    @data(*([_ws.get_spacecraft_list()[0], _ws.get_spacecraft_list()[10], _ws.get_spacecraft_list()[21],
             _ws.get_spacecraft_list()[50], _ws.get_spacecraft_list()[100], _ws.get_spacecraft_list()[130],
             _ws.get_spacecraft_list()[-5]] + _ws.get_comet_list() + _ws.get_asteroid_list() + _ws.get_planet_list()))
    def test_can_get_trajectory(self, body):
        start = body.coverage['startTime'] + timedelta(days=10)
        stop = start + timedelta(days=1)
        traj = _ws.get_orbit_data(body=body,
                                  start_time=start,
                                  stop_time=stop)
        self.assertIsNotNone(traj, msg=f"Body is {body.name}   id:{body.naif_id}")
        self.assertGreater(len(traj), timedelta(days=1).total_seconds() / 60)

    @data(_ws.get_spacecraft_list()[20])
    def test_broken_get_trajectory(self, body):
        start = body.coverage['startTime'] + timedelta(days=10)
        stop = start + timedelta(days=1)
        traj = _ws.get_orbit_data(body=body,
                                  start_time=start,
                                  stop_time=stop)
        self.assertIsNone(traj)
