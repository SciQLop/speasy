import logging
import os
import unittest
from datetime import datetime, timedelta, timezone
from multiprocessing import dummy

import numpy as np
from ddt import data, ddt

from speasy import cda


@ddt
class SimpleRequest(unittest.TestCase):
    def setUp(self):
        if "GITHUB_ACTION" in os.environ  and os.environ.get("RUNNER_OS")=="Windows":
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
        }
    )
    def test_get_variable(self, kw):
        result = cda.get_variable(**kw, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        result = cda.get_variable(**kw, disable_proxy=True, disable_cache=False)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)

    def test_get_simple_vector(self):
        logging.root.addHandler(logging.StreamHandler())
        logging.root.setLevel(logging.DEBUG)
        result1 = cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result1)
        self.assertGreater(len(result1), 0)
        result2 = cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=False)
        self.assertIsNotNone(result2)
        self.assertTrue(np.all(result1.values == result2.values))
        result3 = cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                       start_time=datetime(2014, 6, 1, 10, tzinfo=timezone.utc),
                                       stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                       disable_cache=False)
        self.assertIsNotNone(result3)
        self.assertTrue(np.all(result2.values == result3.values))

    def test_get_empty_vector(self):
        # this used to fail because CDA returns at least a record but removes one dimension from data
        result = cda.get_variable(dataset="THA_L2_FGM", variable="tha_fge_dsl",
                                      start_time=datetime(2014, 6, 1, 23, tzinfo=timezone.utc),
                                      stop_time=datetime(2014, 6, 2, 0, 10, tzinfo=timezone.utc), disable_proxy=True,
                                      disable_cache=True)
        self.assertIsNone(result)

    def test_no_data_404_error(self):
        # this used to fail because CDA returns a 404 error
        result = cda.get_variable(dataset="PSP_FLD_L2_DFB_DBM_SCM", variable="psp_fld_l2_dfb_dbm_scmlgu_rms",
                                      start_time="2020-01-01",
                                      stop_time="2020-01-01T09", disable_proxy=True,
                                      disable_cache=True)
        self.assertIsNone(result)

    def test_data_has_not_been_modified_since_a_short_period(self):
        result = cda.get_variable(dataset='THA_L2_FGM', variable='tha_fgl_gsm',
                                      start_time=datetime(2014, 6, 1, tzinfo=timezone.utc),
                                      stop_time=datetime(2014, 6, 1, 1, 10, tzinfo=timezone.utc), disable_proxy=True,
                                      disable_cache=True, if_newer_than=datetime.utcnow())
        self.assertIsNone(result)

    def test_data_must_have_been_modified_since_a_long_period(self):
        result = cda.get_variable(dataset='THA_L2_FGM', variable='tha_fgl_gsm',
                                      start_time=datetime(2014, 6, 1, tzinfo=timezone.utc),
                                      stop_time=datetime(2014, 6, 1, 1, 10, tzinfo=timezone.utc), disable_proxy=True,
                                      disable_cache=True, if_newer_than=datetime.utcnow() - timedelta(days=50 * 365))
        self.assertIsNotNone(result)

    def test_returns_none_for_a_request_outside_of_range(self):
        with self.assertLogs('speasy.core.dataprovider', level='WARNING') as cm:
            result = cda.get_variable(dataset='THA_L2_FGM', variable='tha_fgl_gsm',
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
            cda.get_variable(dataset="THA_L2_FGM", variable="tha_fgl_gsm", start_time="2018-01-01",
                                 stop_time="2018-01-02", **kwargs)


class ConcurrentRequests(unittest.TestCase):

    def test_get_variable(self):
        def func(i):
            return cda.get_variable(dataset="MMS2_SCM_SRVY_L2_SCSRVY", variable="mms2_scm_acb_gse_scsrvy_srvy_l2",
                                        start_time=datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc),
                                        stop_time=datetime(2016, 6, 1, 0, 20, tzinfo=timezone.utc), disable_proxy=True,
                                        disable_cache=True)

        with dummy.Pool(6) as pool:
            results = pool.map(func, [1] * 10)
        for result in results:
            self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
