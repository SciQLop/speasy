#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import unittest
from datetime import datetime, timezone
import speasy as spz
from ddt import ddt, data


@ddt
class GetSpwc(unittest.TestCase):
    def setUp(self):
        self.proxy_state = spz.config.proxy_enabled.get()
        spz.config.proxy_enabled.set("true")
        spz.config.proxy_url.set("http://sciqlop.lpp.polytechnique.fr/cache")

    def tearDown(self):
        spz.config.proxy_enabled.set(self.proxy_state)

    @data(
        {
            "product": "cdaweb/MMS2_SCM_SRVY_L2_SCSRVY/mms2_scm_acb_gse_scsrvy_srvy_l2",
            "start_time": datetime(2016, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": "cda/THA_L2_FGM/tha_fgl_gsm",
            "start_time": datetime(2014, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2014, 6, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": "cdaweb/THA_L2_FGM/tha_fgl_gsm",
            "start_time": datetime(2015, 6, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2015, 6, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": False
        },
        {
            "product": "amda/c1_hia_prest",
            "start_time": datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": "amda/c1_b_gsm",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": "amda/c1_b_gsm",
            "start_time": datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc),
            "disable_proxy": False
        },
        {
            "product": "sscweb/moon",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": "csa/C1_PP_PEA/T_e_par__C1_PP_PEA",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 2, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": spz.inventory.data_tree.amda.Parameters.THEMIS.THEMIS_A.FGM.tha_fgm_s.tha_bs_gsm,
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 10, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": spz.inventory.data_tree.amda.Catalogs.SharedCatalogs.MARS.MEXShockCrossings
        },
        {
            "product": spz.inventory.data_tree.amda.TimeTables.SharedTimeTables.EARTH.Event_list_tail_hall_reconnection_SC1
        },
        {
            "product": spz.inventory.data_tree.ssc.Trajectories.ace,
            "start_time": '2018-06-01',
            "stop_time": '2018-06-02'
        }
    )
    def test_get_data(self, kw):
        result = spz.get_data(**kw,
                              disable_cache=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    def test_get_data_wrong_path(self):
        with self.assertRaises(ValueError):
            spz.get_data('wrong/path', datetime.now(), datetime.now())

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
        result = spz.get_orbit(**kw,
                               debug=True,
                               disable_cache=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
