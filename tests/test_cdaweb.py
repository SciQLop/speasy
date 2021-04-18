import unittest
from ddt import ddt, data
from datetime import datetime, timezone
from multiprocessing import dummy
import spwc.cdaweb as cd
from spwc.cdaweb import cdaweb
from spwc.cache import Cache
import tempfile
import shutil


@ddt
class SimpleRequest(unittest.TestCase):
    def setUp(self):
        self.default_cache_path = cd._cache._data.directory
        self.cache_path = tempfile.mkdtemp()
        cd._cache = Cache(self.cache_path)
        self.cd = cdaweb()

    def tearDown(self):
        cd._cache = Cache(self.default_cache_path)
        shutil.rmtree(self.cache_path)

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
        result = self.cd.get_variable(**kw, disable_proxy=True, disable_cache=True)
        self.assertIsNotNone(result)


class ConcurrentRequests(unittest.TestCase):
    def setUp(self):
        self.cd = cdaweb()

    def tearDown(self):
        pass

    def test_get_variable(self):
        def func(i):
            return self.cd.get_variable(dataset="MMS2_SCM_SRVY_L2_SCSRVY", variable="mms2_scm_acb_gse_scsrvy_srvy_l2",
                                        start_time=datetime(2016, 6, 1, 0, 10, tzinfo=timezone.utc),
                                        stop_time=datetime(2016, 6, 1, 0, 20, tzinfo=timezone.utc), disable_proxy=True,
                                        disable_cache=True, fmt="csv")

        with dummy.Pool(2) as pool:
            results = pool.map(func, [1] * 8)
        for result in results:
            self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
