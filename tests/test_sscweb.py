#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import unittest
from datetime import datetime, timezone
from speasy.webservices import ssc
from astropy import units
from ddt import ddt, data


@ddt
class SscWeb(unittest.TestCase):
    def setUp(self):
        self.ssc = ssc.SSC_Webservice()

    def tearDown(self):
        pass

    @data(
        {
            "product": "moon",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "bepicolombo",
            "start_time": datetime(2019, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2019, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc),
            "coordinate_system": "GSE"
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc),
            "coordinate_system": "gse"
        }
    )
    def test_get_orbit(self, kw):
        result = self.ssc.get_orbit(**kw,
                                    debug=True,
                                    disable_cache=True,
                                    disable_proxy=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        self.assertGreater(60., kw["start_time"].timestamp() - result.time[0])
        self.assertGreater(60., kw["stop_time"].timestamp() - result.time[-1])

    def test_get_data_from_cache_preserve_unit(self):
        # https://github.com/SciQLop/speasy/issues/7
        for _ in range(3):
            result = self.ssc.get_orbit('moon', datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
                                        datetime(2006, 1, 8, 2, 0, 0, tzinfo=timezone.utc))
            self.assertIs(type(result.values), units.quantity.Quantity)

    def test_get_observatories(self):
        obs_list = self.ssc.get_observatories()
        self.assertIsNotNone(obs_list)
        self.assertGreater(len(obs_list), 10)  # it has to return few elements

    @data({'sampling': '1'},
          {'unknown_arg': 10})
    def test_raises_if_user_passes_unexpected_kwargs_to_get_orbit(self, kwargs):
        with self.assertRaises(TypeError):
            self.ssc.get_orbit('moon', "2018-01-01", "2018-01-02", **kwargs)
