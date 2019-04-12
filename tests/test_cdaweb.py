import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timezone
from multiprocessing import dummy

from spwc.cdaweb import cdaweb

@ddt
class simple_request(unittest.TestCase):
    def setUp(self):
        self.cd = cdaweb()

    def tearDown(self):
        pass

    @data(
        {
            "dataset":"MMS2_SCM_SRVY_L2_SCSRVY",
            "variable":"mms2_scm_acb_gse_scsrvy_srvy_l2",
            "tstart":datetime(2016, 6, 1, tzinfo=timezone.utc),
            "tend":datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc)
        },
        {
            "dataset": "THA_L2_FGM",
            "variable": "tha_fgl_gsm",
            "tstart": datetime(2014, 6, 1, tzinfo=timezone.utc),
            "tend": datetime(2014, 6, 1, 1, 10, tzinfo=timezone.utc)
        }
    )
    def test_get_variable(self,kw):
        result = self.cd.get_variable(**kw)
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
                                        tstart=datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc),
                                        tend=datetime(2016, 6, 1, 0, 20, tzinfo=timezone.utc))

        results = self.pool.map(func, [1] * 8)
        for result in results:
            self.assertIsNotNone(result)
