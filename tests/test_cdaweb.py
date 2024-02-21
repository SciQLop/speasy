import logging
import os
import unittest
from datetime import datetime, timedelta, timezone
from multiprocessing import dummy

import numpy as np
import speasy as spz
from ddt import data, ddt


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
            "dataset": "ERG_ORB_L3",
            "variable": "pos_eq_op",
            "start_time": datetime(2018, 1, 1, tzinfo=timezone.utc),
            "stop_time": datetime(2018, 1, 1, 2, tzinfo=timezone.utc)
        }
    )
    def test_get_variable(self, kw):
        result = spz.cda.get_variable(**kw, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        result = spz.cda.get_variable(**kw, disable_proxy=True, disable_cache=False)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        self.assertEqual(len(result.columns), result.values.shape[1])

    def test_get_simple_vector(self):
        logging.root.addHandler(logging.StreamHandler())
        logging.root.setLevel(logging.DEBUG)
        result1 = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result1)
        self.assertGreater(len(result1), 0)
        result2 = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=False)
        self.assertIsNotNone(result2)
        self.assertTrue(np.all(result1.values == result2.values))
        result3 = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=False)
        self.assertIsNotNone(result3)
        self.assertTrue(np.all(result2.values == result3.values))

    def test_get_empty_vector(self):
        # this used to fail because CDA returns at least a record but removes one dimension from data
        result = spz.cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                      start_time=datetime(2014, 6, 1, 23, tzinfo=timezone.utc),
                                      stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                      disable_cache=True)
        self.assertIsNone(result)

    def test_no_data_404_error(self):
        # this used to fail because CDA returns a 404 error
        result = spz.cda.get_variable(dataset="PSP_FLD_L2_DFB_DBM_SCM", variable="psp_fld_l2_dfb_dbm_scmlgu_rms",
                                      start_time="2020-01-01",
                                      stop_time="2020-01-01T09", disable_proxy=True,
                                      disable_cache=True)
        self.assertIsNone(result)

    def test_data_has_not_been_modified_since_a_short_period(self):
        result = spz.cda.get_variable(dataset='THA_L2_FGM', variable='tha_fgl_gsm',
                                      start_time=datetime(2014, 6, 1, tzinfo=timezone.utc),
                                      stop_time=datetime(2014, 6, 1, 1, 10, tzinfo=timezone.utc), disable_proxy=True,
                                      disable_cache=True, if_newer_than=datetime.utcnow())
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
        spz.core.index.index.set("cdaweb-inventory", "masters-last-modified", "")
        spz.core.index.index.set("cdaweb-inventory", "xml_catalog-last-modified", "")
        if spz.core.index.index.contains("cdaweb-inventory", "tree"):
            spz.core.index.index.pop("cdaweb-inventory", "tree")
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


if __name__ == '__main__':
    unittest.main()
