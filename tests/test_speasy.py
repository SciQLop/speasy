#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import os
import unittest
from datetime import datetime, timezone

from ddt import data, ddt, unpack

import speasy as spz
from speasy.core.dataprovider import PROVIDERS


@ddt
class SpeasyGetData(unittest.TestCase):
    def setUp(self):
        self.proxy_state = spz.config.proxy.enabled()
        spz.config.proxy.enabled.set("true")
        spz.config.proxy.url.set(
            "http://sciqlop.lpp.polytechnique.fr/cache-dev")

    def tearDown(self):
        spz.config.proxy.enabled.set(self.proxy_state)

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
            "start_time": datetime(2015, 6, 1, 23, 50, tzinfo=timezone.utc),
            "stop_time": datetime(2015, 6, 2, 0, 10, tzinfo=timezone.utc),
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
            "product": "csa/C1_CP_EFW_L3_P/Spacecraft_potential__C1_CP_EFW_L3_P",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 2, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": spz.inventories.data_tree.amda.Parameters.THEMIS.THEMIS_A.FGM.tha_fgm_s.tha_bs_gsm,
            "start_time": datetime(2008, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2008, 1, 8, 3, 0, 0, tzinfo=timezone.utc),
            "disable_proxy": True
        },
        {
            "product": spz.inventories.data_tree.amda.Catalogs.SharedCatalogs.MARS.MEXShockCrossings
        },
        {
            "product": spz.inventories.data_tree.amda.TimeTables.SharedTimeTables.EARTH.Event_list_tail_hall_reconnection_SC1
        },
        {
            "product": spz.inventories.data_tree.ssc.Trajectories.ace,
            "start_time": '2018-06-01',
            "stop_time": '2018-06-02'
        }
    )
    def test_get_data(self, kw):
        if "GITHUB_ACTION" in os.environ  and os.environ.get("RUNNER_OS")=="Windows":
            self.skipTest("skip weirdly failing tests on windows")
        result = spz.get_data(**kw,
                              disable_cache=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    def test_get_several_product_on_several_ranges(self):
        result = spz.get_data(
            [spz.inventories.data_tree.ssc.Trajectories.ace,
                "cda/THA_L2_FGM/tha_fgl_gsm"],
            [['2018-06-01', '2018-06-01T01'], ['2018-06-03', '2018-06-03T01']]
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 2)
        self.assertEqual(len(result[1]), 2)

    def test_get_data_wrong_path(self):
        with self.assertRaises(ValueError):
            spz.get_data('wrong/path', datetime.now(), datetime.now())


@ddt
class SpeasyModule(unittest.TestCase):
    def test_can_list_providers(self):
        l = spz.list_providers()
        self.assertListEqual(
            l, ['amda', 'cdaweb', 'cda', 'sscweb', 'ssc', 'csa'])

    @data(*[(provider,) for provider in PROVIDERS.keys()])
    @unpack
    def test_can_update_inventories(self, provider):
        spz.inventories.flat_inventories.__dict__[provider].parameters.clear()
        spz.__dict__[provider].update_inventory()
        self.assertGreaterEqual(
            len(spz.inventories.flat_inventories.__dict__[provider].parameters), 1)

    def test_can_update_inventories_all_at_once(self):
        for provider in PROVIDERS.keys():
            spz.inventories.flat_inventories.__dict__[
                provider].parameters.clear()

        spz.update_inventories()

        for provider in PROVIDERS.keys():
            self.assertGreaterEqual(
                len(spz.inventories.flat_inventories.__dict__[provider].parameters), 1)

    def test_raises_if_product_path_is_broken(self):
        with self.assertRaises(ValueError):
            spz.get_data('this_misses_a_slash', datetime.now(), datetime.now())

    def test_raises_if_product_is_worng_type(self):
        with self.assertRaises(TypeError):
            spz.get_data(None, datetime.now(), datetime.now())
            
    def test_warns_if_proxy_is_disabled(self):
        import importlib
        spz.config.proxy.enabled.set("false")
        with self.assertWarns(UserWarning):
            importlib.reload(spz.core.proxy)
        spz.config.proxy.enabled.set("true")
        importlib.reload(spz.core.proxy)
        
