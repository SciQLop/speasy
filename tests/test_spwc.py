#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `spwc` package."""
import unittest
from datetime import datetime, timezone
import spwc
from ddt import ddt, data


class AMDARequest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_variable(self):
        start_date = datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        result = spwc.get_data("amda/c1_b_gsm", start_date, stop_date, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)
        start_date = datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        parameter_id = "c1_hia_prest"
        result = spwc.get_data("amda/c1_hia_prest", start_date, stop_date, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)


@ddt
class CDARequest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        {
            "dataset": "MMS2_SCM_SRVY_L2_SCSRVY",
            "variable": "mms2_scm_acb_gse_scsrvy_srvy_l2",
            "start_time": datetime(2016, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc)
        },
        {
            "dataset": "THA_L2_FGM",
            "variable": "tha_fgl_gsm",
            "start_time": datetime(2014, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2014, 6, 1, 1, 10, tzinfo=timezone.utc)
        }
    )
    def test_get_variable(self, kw):
        result = spwc.get_data(f'cdaweb/{kw["dataset"]}/{kw["variable"]}', kw["start_time"], kw["stop_time"],
                               disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)
