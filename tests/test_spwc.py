#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `spwc` package."""
import unittest
from datetime import datetime, timezone
import spwc
from ddt import ddt, data


@ddt
class GetSpwc(unittest.TestCase):
    def setUp(self):
        spwc.config.proxy_enabled.set("true")
        spwc.config.proxy_url.set("http://sciqlop.lpp.polytechnique.fr/cache")

    def tearDown(self):
        pass

    @data(
        {
            "path": "cdaweb/MMS2_SCM_SRVY_L2_SCSRVY/mms2_scm_acb_gse_scsrvy_srvy_l2",
            "start_time": datetime(2016, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "path": "cdaweb/THA_L2_FGM/tha_fgl_gsm",
            "start_time": datetime(2014, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2014, 6, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "path": "cdaweb/THA_L2_FGM/tha_fgl_gsm",
            "start_time": datetime(2015, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2015, 6, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": False
        },
        {
            "path": "amda/c1_hia_prest",
            "start_time": datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "path": "amda/c1_b_gsm",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "path": "amda/c1_b_gsm",
            "start_time": datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": False
        },
        {
            "path": "sscweb/moon",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        }
    )
    def test_get_data(self, kw):
        result = spwc.get_data(**kw,
                               disable_cache=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    def test_get_data_wrong_path(self):
        with self.assertRaises(ValueError):
            spwc.get_data('wrong/path',datetime.now(),datetime.now())

    @data(
        {
            "body": "moon",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "body": "bepicolombo",
            "start_time": datetime(2019, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2019, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "body": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        }
    )
    def test_get_orbit(self, kw):
        result = spwc.get_orbit(**kw,
                                debug=True,
                                disable_cache=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
