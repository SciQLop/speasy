#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `spwc` package."""
import unittest
from datetime import datetime, timezone
from spwc import sscweb
from ddt import ddt, data


@ddt
class SscWeb(unittest.TestCase):
    def setUp(self):
        self.ssc = sscweb.SscWeb()

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
        }
    )
    def test_get_orbit(self, kw):
        result = self.ssc.get_orbit(**kw,
                                    debug=True,
                                    disable_cache=True,
                                    disable_proxy=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    def test_get_observatories(self):
        obs_list = self.ssc.get_observatories()
        self.assertIsNotNone(obs_list)
        self.assertGreater(len(obs_list), 10)  # it has to return few elements
