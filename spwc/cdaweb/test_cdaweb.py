import unittest
from typing import List
from ddt import ddt, data, unpack
from datetime import datetime, timedelta
from spwc.cdaweb import cdaweb

import tempfile
import shutil
from multiprocessing import dummy


class simple_request(unittest.TestCase):
    def setUp(self):
        self.cd = cdaweb()

    def tearDown(self):
        pass

    def test_get_variable(self):
        result = self.cd.get_variable(dataset="MMS2_SCM_SRVY_L2_SCSRVY", variable="mms2_scm_acb_gse_scsrvy_srvy_l2",
                                      tstart=datetime(2016, 6, 1), tend=datetime(2016, 6, 1, 0, 10))
        self.assertIsNotNone(result)


class ConcurrentRequests(unittest.TestCase):
    def setUp(self):
        self.cd = cdaweb()
        self.pool = dummy.Pool(8)

    def tearDown(self):
        pass

    def test_get_variable(self):
        def func(i):
            return self.cd.get_variable(dataset="MMS2_SCM_SRVY_L2_SCSRVY", variable="mms2_scm_acb_gse_scsrvy_srvy_l2",
                                        tstart=datetime(2016, 6, 1, 0, 10), tend=datetime(2016, 6, 1, 0, 20))

        results = data = self.pool.map(func, [1] * 8)
        for result in results:
            self.assertIsNotNone(result)
