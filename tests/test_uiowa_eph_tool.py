#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import os
import unittest
from datetime import datetime, timezone
import numpy as np
from ddt import data, ddt, unpack
from keyring.core import disable

import speasy as spz
from speasy.data_providers import uiowa_eph_tool
from speasy.products import SpeasyVariable

_HERE_ = os.path.dirname(os.path.abspath(__file__))

_CSV_SAMPLE_PATH1 = os.path.join(_HERE_, 'resources', 'uiowa_eph_tool_sample.csv')
_CSV_SAMPLE_PATH2 = os.path.join(_HERE_, 'resources', 'uiowa_eph_tool_sample2.csv')

@ddt
class SscUiowaEphTool(unittest.TestCase):
    def setUp(self):
        self.uiowa = uiowa_eph_tool.UiowaEphTool()



    @data(

            (_CSV_SAMPLE_PATH1, spz.inventories.tree.uiowaephtool.Trajectories.Callisto.Co_rotational.Cassini, 13, np.datetime64('2004-07-01T02:00:00.000000000', 'ns'), np.datetime64('2004-07-01T03:00:00.000000000', 'ns')),
            (_CSV_SAMPLE_PATH2, spz.inventories.tree.uiowaephtool.Trajectories.Callisto.Co_rotational.Cassini, 61, np.datetime64('2000-01-01T02:00:00.000000000', 'ns'), np.datetime64('2000-01-01T03:00:00.000000000', 'ns'))

    )
    @unpack
    def test_parses_csv_result(self, fname, product, data_rows, start_time, stop_time):
        with open(fname, 'r') as f:
            eph = uiowa_eph_tool.parse_trajectory(f.read(), product)
            self.assertIsNotNone(eph)
            self.assertEqual(len(eph), data_rows)
            self.assertEqual(eph.time[0], start_time)
            self.assertEqual(eph.time[-1], stop_time)


    @data(
        (spz.inventories.tree.uiowaephtool.Trajectories.Callisto.Co_rotational.Cassini, "2006-01-08T00:00:00", "2006-01-09T00:00:00"),
        ('Callisto_Cassini_Co-rotational', "2006-01-08T00:00:00", "2006-01-09T00:00:00"),
        (spz.inventories.tree.uiowaephtool.Trajectories.Sun.Ecliptic.Cassini, "2006-01-08T00:00:00", "2006-01-09T00:00:00"),
        ('Sun_Cassini_Ecliptic', "2006-01-08T00:00:00", "2006-01-09T00:00:00"),
        (spz.inventories.tree.uiowaephtool.Trajectories.Jupiter.Ecliptic.Io, "2006-01-08T00:00:00", "2006-01-09T00:00:00"),
        ('Jupiter_Io_Ecliptic', "2006-01-08T00:00:00", "2006-01-09T00:00:00"),
        (spz.inventories.tree.uiowaephtool.Trajectories.Io.Geographic.Galileo, "2000-01-08T00:00:00", "2000-01-09T00:00:00"),
    )
    @unpack
    def test_simple_request(self, trajectory, start, end):
        eph = self.uiowa.get_data(trajectory, start, end, disable_cache=True)
        self.assertIsNotNone(eph)
        self.assertGreater(len(eph), 0)
        self.assertIsInstance(eph, SpeasyVariable)
        self.assertIn('COORDINATE_SYSTEM', eph.meta)

