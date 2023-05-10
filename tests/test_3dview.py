#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `cdpp_3dview` package."""
import os
import unittest
from datetime import timedelta

import numpy as np
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

    @data((spz.inventories.tree.ssc.Trajectories.ace, "GSE"),
          (spz.inventories.tree.ssc.Trajectories.mms1, "GSE"),
          #(spz.inventories.tree.ssc.Trajectories.mms1, "GSM"),
          (spz.inventories.tree.ssc.Trajectories.themisa, "GSM"),
          (spz.inventories.tree.ssc.Trajectories.bepicolombo, "GSE"),
          )
    @unpack
    def test_compare_ssc_trajectory(self, ssc_index, coordinate_system):
        start_time = spz.core.make_utc_datetime("2021-01-01")
        stop_time = spz.core.make_utc_datetime("2021-01-05")
        ssc_data = spz.get_data(ssc_index, start_time, stop_time,
                                coordinate_system=coordinate_system)
        self.assertIsNotNone(ssc_data)
        ssc_data = ssc_data.to_dataframe()

        cdpp_3DView_data = _ws.get_orbit_data(body=find_body(ssc_index.Id),
                                              start_time=start_time,
                                              stop_time=stop_time,
                                              frame=find_frame(coordinate_system),
                                              time_vector=list(
                                                  map(spz.core.make_utc_datetime, ssc_data.index.to_pydatetime())))

        self.assertIsNotNone(cdpp_3DView_data)

        cdpp_3DView_data = cdpp_3DView_data.to_dataframe()

        ssc_data.columns = cdpp_3DView_data.columns
        abs_error = abs(ssc_data - cdpp_3DView_data)
        percent_error = 100 * abs((ssc_data - cdpp_3DView_data) / ssc_data)
        self.assertLess(percent_error.median().max(), 0.5)
        self.assertTrue(np.all(abs(abs_error.loc[percent_error.x > 0.5].x) < 200))
        self.assertTrue(np.all(abs(abs_error.loc[percent_error.y > 0.5].y) < 200))
        self.assertTrue(np.all(abs(abs_error.loc[percent_error.z > 0.5].z) < 200))
