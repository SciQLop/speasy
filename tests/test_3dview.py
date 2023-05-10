#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `cdpp_3dview` package."""
import os
import unittest
from datetime import timedelta

from ddt import data, ddt, unpack

import speasy as spz
from speasy.webservices.cdpp_3dview.trajectory_loader import load_trajectory
from speasy.webservices.cdpp_3dview.ws import _WS_impl

_ws = _WS_impl()


def find_body(name: str):
    bodies = _ws.get_spacecraft_list()
    for body in bodies:
        if body.name == name or body.name.lower() == name.lower():
            return body
    return None


def find_frame(name: str):
    frames = _ws.get_frame_list()
    for frame in frames:
        if frame.name == name or frame.name.lower() == name.lower():
            return frame
    return None


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
             _ws.get_spacecraft_list()[-5]] + _ws.get_comet_list() + _ws.get_asteroid_list()))
    def test_can_get_trajectory(self, body):
        start = body.coverage['startTime'] + timedelta(days=10)
        stop = start + timedelta(days=1)
        traj = _ws.get_orbit_data(body=body,
                                  start_time=start,
                                  stop_time=stop)
        self.assertIsNotNone(traj, msg=f"Body is {body.name}   id:{body.naif_id}")
        self.assertGreater(len(traj), timedelta(days=1).total_seconds() / 60)

    def test_loads_a_valid_trajectory_votable(self):
        v = load_trajectory(f'{os.path.dirname(os.path.abspath(__file__))}/resources/3DViewSampleTrajectory.vot.gz')
        self.assertIsNotNone(v)

    def test_compare_ssc_trajectory(self):
        start_time = spz.core.make_utc_datetime("2018-01-01")
        stop_time = spz.core.make_utc_datetime("2018-01-05")
        ace_ssc_gse = spz.get_data(spz.inventories.tree.ssc.Trajectories.ace, start_time, stop_time,
                                   coordinate_system="GSE")

        ace_3DView_gse = _ws.get_orbit_data(body=find_body('ace'),
                                            start_time=start_time,
                                            stop_time=stop_time, frame=find_frame('GSE'))

        self.assertIsNotNone(ace_ssc_gse)
        self.assertIsNotNone(ace_3DView_gse)
