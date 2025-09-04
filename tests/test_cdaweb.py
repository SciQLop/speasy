import logging
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from multiprocessing import dummy

import numpy as np
import speasy as spz
from speasy.data_providers.cda._direct_archive import to_direct_archive_params
from speasy.core.direct_archive_downloader.direct_archive_downloader import apply_date_format
from ddt import data, ddt, unpack


def reset_cda_inventory_cache_flags():
    spz.core.index.index.set("cdaweb-inventory", "masters-last-modified", "")
    spz.core.index.index.set("cdaweb-inventory", "xml_catalog-last-modified", "")
    if spz.core.index.index.contains("cdaweb-inventory", "tree"):
        spz.core.index.index.pop("cdaweb-inventory", "tree")

@ddt
class SimpleRequest(unittest.TestCase):
    def setUp(self):
        if "GITHUB_ACTION" in os.environ and os.environ.get("RUNNER_OS") == "Windows":
            self.skipTest("skip weirdly failing tests on windows")

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
            "start_time": datetime(2014, 6, 1, 23, tzinfo=timezone.utc),
            "stop_time": datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc)
        },
        {
            "dataset": "WI_K0_SMS",
            "variable": "C/O_ratio",
            "start_time": datetime(1996, 8, 1, 20, tzinfo=timezone.utc),
            "stop_time": datetime(1996, 8, 1, 23, tzinfo=timezone.utc)
        },
        {
            "dataset": "MMS1_SCM_BRST_L2_SCB",
            "variable": "mms1_scm_acb_gse_scb_brst_l2",
            "start_time": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2020, 1, 1, 2, tzinfo=timezone.utc)
        },
        {
            "dataset": "ERG_ORB_L2",
            "variable": "pos_gse",
            "start_time": datetime(2018, 1, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2018, 1, 1, 2, tzinfo=timezone.utc)
        }
    )
    def test_get_variable_ws(self, kw):
        result = spz.cda.get_variable(**kw, disable_proxy=True, disable_cache=True, method="API")
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        result = spz.cda.get_variable(**kw, disable_proxy=True, disable_cache=False, method="API")
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        self.assertEqual(len(result.columns), result.values.shape[1])

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
            "start_time": datetime(2014, 6, 1, 23, tzinfo=timezone.utc),
            "stop_time": datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc)
        },
        {
            "dataset": "WI_K0_SMS",
            "variable": "C/O_ratio",
            "start_time": datetime(1996, 8, 1, 20, tzinfo=timezone.utc),
            "stop_time": datetime(1996, 8, 1, 23, tzinfo=timezone.utc)
        },
        {
            "dataset": "MMS1_SCM_BRST_L2_SCB",
            "variable": "mms1_scm_acb_gse_scb_brst_l2",
            "start_time": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2020, 1, 1, 2, tzinfo=timezone.utc)
        },
        {
            "dataset": "ERG_ORB_L2",
            "variable": "pos_gse",
            "start_time": datetime(2018, 1, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2018, 1, 1, 2, tzinfo=timezone.utc)
        },
        {
            "dataset": "SOLO_L2_MAG-RTN-NORMAL-1-MINUTE",
            "variable": "B_RTN",
            "start_time": datetime(2021, 1, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 1, 2, tzinfo=timezone.utc)
        }
    )
    def test_a_simple_direct_archive_request(self, kwargs):
        result = spz.cda.get_variable(**kwargs, disable_proxy=True,
                                      disable_cache=True, method="FILE")
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    def test_get_simple_vector(self):
        logging.root.addHandler(logging.StreamHandler())
        logging.root.setLevel(logging.DEBUG)
        result1 = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=True, method="API")
        self.assertIsNotNone(result1)
        self.assertGreater(len(result1), 0)
        result2 = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=False, method="API")
        self.assertIsNotNone(result2)
        self.assertTrue(np.all(result1.values == result2.values))
        result3 = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=False, method="API")
        self.assertIsNotNone(result3)
        self.assertTrue(np.all(result2.values == result3.values))

    def test_get_empty_vector(self):
        variable = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                        start_time=datetime(2014, 6, 1, 23,
                                                            tzinfo=timezone.utc),
                                        stop_time=datetime(2014, 6, 2, 0, 10,
                                                           tzinfo=timezone.utc),
                                        disable_proxy=True, disable_cache=True,
                                        method="API")
        # this used to fail because CDA returns at least a record but removes one dimension from data
        self.assertIsNone(variable)

    def test_no_data_404_error(self):
        # this used to fail because CDA returns a 404 error
        result = spz.cda.get_variable(dataset="PSP_FLD_L2_DFB_DBM_SCM", variable="psp_fld_l2_dfb_dbm_scmlgu_rms",
                                      start_time="2020-01-01",
                                      stop_time="2020-01-01T09", disable_proxy=True,
                                      disable_cache=True, method="API")
        self.assertIsNone(result)

    def test_data_has_not_been_modified_since_a_short_period(self):
        result = spz.cda.get_variable(dataset='THA_L2_FGM', variable='tha_fgl_gsm',
                                      start_time=datetime(2014, 6, 1, tzinfo=timezone.utc),
                                      stop_time=datetime(2014, 6, 1, 1, 10, tzinfo=timezone.utc), disable_proxy=True,
                                      disable_cache=True, if_newer_than=datetime.utcnow(), method="API")
        self.assertIsNone(result)

    def test_data_must_have_been_modified_since_a_long_period(self):
        result = spz.cda.get_variable(dataset='THA_L2_FGM', variable='tha_fgl_gsm',
                                      start_time=datetime(2014, 6, 1, tzinfo=timezone.utc),
                                      stop_time=datetime(2014, 6, 1, 1, 10, tzinfo=timezone.utc), disable_proxy=True,
                                      disable_cache=True, if_newer_than=datetime.utcnow() - timedelta(days=50 * 365))
        self.assertIsNotNone(result)

    def test_returns_none_for_a_request_outside_of_range(self):
        with self.assertLogs('speasy.core.dataprovider', level='WARNING') as cm:
            result = spz.cda.get_variable(dataset='THA_L2_FGM', variable='tha_fgl_gsm',
                                          start_time=datetime(2000, 6, 1, tzinfo=timezone.utc),
                                          stop_time=datetime(2000, 6, 1, 1, 10, tzinfo=timezone.utc),
                                          disable_proxy=True,
                                          disable_cache=True)
            self.assertIsNone(result)
            self.assertTrue(
                any(["outside of its definition range" in line for line in cm.output]))

    @data({'sampling': '1'},
          {'unknown_arg': 10})
    def test_raises_if_user_passes_unexpected_kwargs_to_get_variable(self, kwargs):
        with self.assertRaises(TypeError):
            spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fgl_gsm", start_time="2018-01-01",
                                 stop_time="2018-01-02", **kwargs)

    def test_can_get_full_inventory_without_proxy(self):
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        reset_cda_inventory_cache_flags()
        spz.cda.update_inventory()
        os.environ.pop(spz.config.proxy.enabled.env_var_name)
        self.assertGreaterEqual(len(spz.inventories.flat_inventories.cda.parameters), 47000)


class ConcurrentRequests(unittest.TestCase):

    def test_get_variable(self):
        def func(i):
            return spz.cda.get_variable(dataset="MMS2_SCM_SRVY_L2_SCSRVY", variable="mms2_scm_acb_gse_scsrvy_srvy_l2",
                                        start_time=datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc),
                                        stop_time=datetime(2016, 6, 1, 0, 20, tzinfo=timezone.utc), disable_proxy=True,
                                        disable_cache=True)

        with dummy.Pool(6) as pool:
            results = pool.map(func, [1] * 10)
        for result in results:
            self.assertIsNotNone(result)


class SpecificNonRegression(unittest.TestCase):

    def test_dots_are_replaced_by_dollars(self):
        result = spz.get_data("cda/WI_PLSP_3DP/MOM.P.MAGF", "2018-01-01", "2018-01-02", disable_proxy=True,
                              disable_cache=True)
        self.assertIsNotNone(result)

    def test_broken_var_saved_into_cache(self):
        for i in range(2):
            v = spz.get_data(spz.inventories.tree.cda.ACE.MAG.AC_H2_MFI.BGSEc, "2018-01-01", "2018-01-02")
            self.assertIsNotNone(v)

    def test_get_dataset_raises_an_understandable_error_message(self):
        with self.assertRaises(ValueError) as cm:
            solo_swa = spz.get_data(spz.inventories.tree.cda.Solar_Orbiter.SOLO.SWA_PAS.SOLO_L2_SWA_PAS_GRND_MOM,
                                    "2021-11-3",
                                    "2021-11-4")
            self.assertIn("Can't directly download a whole dataset from cda", str(cm.exception))

    def test_get_an_unknown_parameter_raises_the_right_error_message(self):
        with self.assertRaises(ValueError) as cm:
            solo_swa = spz.get_data("cda/wrong/data", "2021-11-3", "2021-11-4")
            self.assertIn("Unknown parameter:", str(cm.exception))

    def test_get_virtual_parameter_always_falls_back_to_api(self):
        mms1_fgm_b_bcs_srvy_l2_clean = spz.get_data(
            spz.inventories.tree.cda.MMS.MMS1.FGM.MMS1_FGM_SRVY_L2.mms1_fgm_b_bcs_srvy_l2_clean,
            "2021-11-3", "2021-11-3T01", disable_proxy=True, disable_cache=True, method="FILE")
        self.assertIsNotNone(mms1_fgm_b_bcs_srvy_l2_clean)

    def test_wrong_time_dependency_axis(self):
        result = spz.get_data(
            "cda/MMS1_FEEPS_SRVY_L2_ELECTRON/mms1_epd_feeps_srvy_l2_electron_bottom_intensity_sensorid_2",
            datetime(2018, 5, 26, 1, 0, 0), datetime(2018, 5, 26, 1, 10, 1))
        self.assertIsNotNone(result)

    def test_mms_fgm_sanitized(self):
        # https://github.com/SciQLop/speasy/issues/205
        var = spz.get_data("cda/MMS2_FGM_SRVY_L2/mms2_fgm_b_gse_srvy_l2_clean", "2015-10-16T13:05:30",
                           "2015-10-16T13:07:30")
        var = var.sanitized()
        self.assertIsNotNone(var)

    def test_get_cluster_fgm_data(self):
        # should return None because the data is not available but should not raise an error
        result = spz.get_data(
            spz.inventories.data_tree.cda.Cluster.C1.FGM_SPIN.C1_CP_FGM_SPIN.B_vec_xyz_gse__C1_CP_FGM_SPIN,
            "2018-03-02", "2018-03-03")
        self.assertIsNone(result)

        result = spz.get_data(
            spz.inventories.data_tree.cda.Cluster.C1.FGM_SPIN.C1_CP_FGM_SPIN.B_vec_xyz_gse__C1_CP_FGM_SPIN,
            "2016-03-02", "2016-03-03")
        self.assertIsNone(result)

        result = spz.get_data(
            spz.inventories.data_tree.cda.Cluster.C1.FGM_SPIN.C1_CP_FGM_SPIN.B_vec_xyz_gse__C1_CP_FGM_SPIN,
            "2015-03-02", "2015-03-03")
        self.assertIsNotNone(result)

    def test_get_products_with_percent_in_name(self):
        # https://github.com/SciQLop/speasy/issues/211
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        reset_cda_inventory_cache_flags()
        spz.cda.update_inventory()
        data = spz.get_data(spz.inventories.tree.cda.Equator_S.EQ.MAM.EQ_PP_MAM.B_nsigma_b_eq_pp_mam, "1998-01-01",
                            "1998-01-02")
        self.assertIsNotNone(data)
        os.environ.pop(spz.config.proxy.enabled.env_var_name)

    def test_get_stereo_l1_het(self):
        # https://github.com/SciQLop/speasy/issues/223
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        data = spz.get_data("cda/STA_L1_HET/Proton_Flux", "2020-10-28", "2020-10-28T01")
        self.assertIsNotNone(data)
        os.environ.pop(spz.config.proxy.enabled.env_var_name)

    def test_get_PSP_ISOIS_EPILO_L2_PE(self):
        # https://github.com/SciQLop/speasy/issues/225
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        data = spz.get_data("cda/PSP_ISOIS-EPILO_L2-PE/Electron_Counts_ChanE", "2021-10-09", "2021-10-09T01")
        self.assertIsNotNone(data)
        data_sum_1 = np.sum(data, axis=1)
        data_sum_2 = np.sum(data, axis=2)
        self.assertIsNotNone(data_sum_1)
        self.assertIsNotNone(data_sum_2)

    def test_get_WI_SFSP_3DP(self):
        # https://github.com/SciQLop/speasy/issues/225
        os.environ[spz.config.proxy.enabled.env_var_name] = "False"
        self.assertEqual(spz.inventories.tree.cda.Wind.WIND.n_3DP.WI_SFSP_3DP.FLUX.VIRTUAL.lower(), "true")
        data = spz.get_data("cda/WI_SFSP_3DP/FLUX", "2005-01-01", "2005-01-01T01")
        self.assertIsNotNone(data)


@ddt
class DirectArchiveConverter(unittest.TestCase):

    @data(
        (
            "i8_h0_gme_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/imp/imp8/particles_gme/data/flux/gme_h0",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'i8_h0_gme_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/imp/imp8/particles_gme/data/flux/gme_h0/{Y}/i8_h0_gme_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/imp/imp8/particles_gme/data/flux/gme_h0/1993/i8_h0_gme_19930101_v01.cdf",
            datetime(1993, 3, 3, tzinfo=timezone.utc)
        ),
        (
            "solo_l2_epd-ept-asun-burst-ion_%Y%m%dt%H%M%S-%Y%m%dt%H%M%S_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/epd/science/l2/ept/asun-burst-ion",
            {
                'date_format': '%Y%m%dt%H%M%S',
                'fname_regex': 'solo_l2_epd-ept-asun-burst-ion_(?P<start>\\d+t?T?\\d+)-(?P<stop>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/epd/science/l2/ept/asun-burst-ion/{Y}/solo_l2_epd-ept-asun-burst-ion_{Y}[01]\\d[0-3]\\dt[0-2]\\d[0-5]\\d[0-5]\\d-[12]\\d\\d\\d[01]\\d[0-3]\\dt[0-2]\\d[0-5]\\d[0-5]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/epd/science/l2/ept/asun-burst-ion/2020/solo_l2_epd-ept-asun-burst-ion_20200615t122228-20200615t123728_v02.cdf",
            datetime(2020, 6, 15, 12, 22, 28, tzinfo=timezone.utc)
        ),
        (
            "wi_ehpd_3dp_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/wind/3dp/3dp_ehpd",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'wi_ehpd_3dp_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/wind/3dp/3dp_ehpd/{Y}/wi_ehpd_3dp_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/wind/3dp/3dp_ehpd/2005/wi_ehpd_3dp_20050116_v02.cdf",
            datetime(2005, 1, 16, tzinfo=timezone.utc)
        ),
        (
            "ac_or_def_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/ace/orbit/level_2_cdaweb/def_or",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'ac_or_def_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/ace/orbit/level_2_cdaweb/def_or/{Y}/ac_or_def_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/ace/orbit/level_2_cdaweb/def_or/1997/ac_or_def_19970826_v01.cdf",
            datetime(1997, 8, 26, tzinfo=timezone.utc)
        ),
        (
            "aerocube-6-a_dosimeter_l2_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/aaa_smallsats_cubesats/aerocube/aerocube-6/aerocube6-a/dosimeter-cdf",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'aerocube-6-a_dosimeter_l2_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/aaa_smallsats_cubesats/aerocube/aerocube-6/aerocube6-a/dosimeter-cdf/{Y}/aerocube-6-a_dosimeter_l2_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/aaa_smallsats_cubesats/aerocube/aerocube-6/aerocube6-a/dosimeter-cdf/2017/aerocube-6-a_dosimeter_l2_20170508_v1.0.0.cdf",
            datetime(2017, 5, 8, tzinfo=timezone.utc)
        ),
        (
            "amptecce_h0_mepa_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/ampte/cce/MEPA/h0",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'amptecce_h0_mepa_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/ampte/cce/MEPA/h0/{Y}/amptecce_h0_mepa_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/ampte/cce/MEPA/h0/1986/amptecce_h0_mepa_19860508_v01.cdf",
            datetime(1986, 5, 8, tzinfo=timezone.utc)
        ),
        (
            "apollo12_sws_28s_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/apollo/apollo12_cdaweb/sws_28s",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'apollo12_sws_28s_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/apollo/apollo12_cdaweb/sws_28s/{Y}/apollo12_sws_28s_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/apollo/apollo12_cdaweb/sws_28s/1969/apollo12_sws_28s_19691223_v01.cdf",
            datetime(1969, 12, 23, tzinfo=timezone.utc)
        ),
        (
            "bar_1b_l2_fspc_%Y%m%d_%Q.cdf",
            "None",
            "https://cdaweb.gsfc.nasa.gov/pub/data/barrel/l2/1b/fspc",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'bar_1b_l2_fspc_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'none',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/barrel/l2/1b/fspc/bar_1b_l2_fspc_[12]\\d\\d\\d[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/barrel/l2/1b/fspc/bar_1b_l2_fspc_20130106_v10.cdf",
            datetime(2013, 1, 6, tzinfo=timezone.utc)
        ),
        (
            "cn_k1_mari_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/canopus/mari_rio",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'cn_k1_mari_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/canopus/mari_rio/{Y}/cn_k1_mari_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/canopus/mari_rio/1996/cn_k1_mari_19960101_v01.cdf",
            datetime(1996, 1, 1, tzinfo=timezone.utc)
        ),
        (
            "csswe_reptile_6sec-flux-l2_%Y%m%d_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/csswe/l2/reptile/flux",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'csswe_reptile_6sec-flux-l2_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/csswe/l2/reptile/flux/{Y}/csswe_reptile_6sec-flux-l2_{Y}[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/csswe/l2/reptile/flux/2013/csswe_reptile_6sec-flux-l2_20131126_v01.cdf",
            datetime(2013, 11, 26, tzinfo=timezone.utc)
        ),
        (
            "endurance_ephemeris_def_%Y%m%d_%Q.cdf",
            "None",
            "https://cdaweb.gsfc.nasa.gov/pub/data/sounding_rockets/endurance/endurance-2022/cdf",
            {
                'date_format': '%Y%m%d',
                'fname_regex': 'endurance_ephemeris_def_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'none',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/sounding_rockets/endurance/endurance-2022/cdf/endurance_ephemeris_def_[12]\\d\\d\\d[01]\\d[0-3]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/sounding_rockets/endurance/endurance-2022/cdf/endurance_ephemeris_def_20220511_v01.cdf",
            datetime(2022, 5, 11, tzinfo=timezone.utc)
        ),
        (
            "iss_dosanl_tepc_%Y%m%d%H%M_%Q.cdf",
            "None",
            "https://cdaweb.gsfc.nasa.gov/pub/data/international_space_station_iss/dos_tepc",
            {
                'date_format': '%Y%m%d%H%M',
                'fname_regex': 'iss_dosanl_tepc_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'none',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/international_space_station_iss/dos_tepc/iss_dosanl_tepc_[12]\\d\\d\\d[01]\\d[0-3]\\d[0-2]\\d[0-5]\\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/international_space_station_iss/dos_tepc/iss_dosanl_tepc_201212190402_v01.cdf",
            datetime(2012, 12, 20, tzinfo=timezone.utc)
        ),
        (
            "msl_rad_obs-l2_%Y%j_%Q.cdf",
            "%Y",
            "https://cdaweb.gsfc.nasa.gov/pub/data/aaa_planetary/msl/rad/cdf/obs-l2",
            {
                'date_format': '%Y%j',
                'fname_regex': 'msl_rad_obs-l2_(?P<start>\\d+t?T?\\d+)_(?P<version>.*).cdf',
                'split_frequency': 'yearly',
                'split_rule': 'random',
                'url_pattern': 'https://cdaweb.gsfc.nasa.gov/pub/data/aaa_planetary/msl/rad/cdf/obs-l2/{Y}/msl_rad_obs-l2_{Y}[0-3]\d\d_.*.cdf',
                'use_file_list': True
            },
            "https://cdaweb.gsfc.nasa.gov/pub/data/aaa_planetary/msl/rad/cdf/obs-l2/2015/msl_rad_obs-l2_2015001_v00.cdf",
            datetime(2015, 1, 1, tzinfo=timezone.utc)
        )
    )
    @unpack
    def test_convert_to_direct_archive_params(self, file_naming: str, subdivided_by: str, url: str, expected, test_url,
                                              sample_date):
        result = to_direct_archive_params(file_naming=file_naming, subdivided_by=subdivided_by, url=url)
        self.assertEqual(result, expected)
        fname_regex = re.compile(result['fname_regex'])
        url_pattern = re.compile(apply_date_format(result['url_pattern'], sample_date))
        self.assertIsNotNone(fname_regex.search(test_url))
        self.assertIsNotNone(url_pattern.search(test_url))


if __name__ == '__main__':
    unittest.main()
