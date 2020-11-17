import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.cache.cache import Cache
from spwc.cache import Cacheable, _round_for_cache
from spwc.cache.version import str_to_version, version_to_str
from spwc.common.datetime_range import DateTimeRange
from spwc.common.variable import SpwcVariable
import packaging.version as Version
import dateutil.parser as dt_parser
import operator
import numpy as np

import tempfile
import shutil

start_date = datetime(2016, 6, 1, 12, tzinfo=timezone.utc)

dirpath = tempfile.mkdtemp()
cache = Cache(dirpath)


@ddt
class _CacheTest(unittest.TestCase):
    def setUp(self):
        self._make_data_cntr = 0
        self._version = 0

    def version(self, product):
        return self._version

    @Cacheable(prefix="", cache_instance=cache, version=version, leak_cache=True)
    def _make_data(self, product, start_time, stop_time):
        index = np.array(
            [(start_time + timedelta(minutes=delta)).timestamp() for delta in
             range(int((stop_time - start_time).seconds / 60))])
        data = index / 3600.
        self._make_data_cntr += 1
        return SpwcVariable(time=index, data=data)

    def _get_and_check(self, start, stop):
        var = self._make_data("...", start, stop)
        self.assertIsNotNone(var)
        self.assertEqual(var.time[0], start.timestamp())
        self.assertEqual(var.time[-1], (stop - timedelta(minutes=1)).timestamp())
        self.assertEqual(len(var), (stop - start).seconds / 60)

    @data(
        (start_date, start_date + timedelta(minutes=10), "Less than one hour"),
        (start_date, start_date + timedelta(minutes=70), "More than one hour"),
        (start_date, start_date + timedelta(hours=13), "Over midnight")
    )
    @unpack
    def test_get_data(self, tstart, tend, name):
        self._get_and_check(tstart, tend)

    def test_get_data_more_than_once(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        stats = self._make_data.cache.stats()
        for _ in range(10):
            var = self._make_data("test_get_data_more_than_once", tstart,
                                  tend)  # self.cache.get_data("test_get_data_more_than_once", DateTimeRange(tstart, tend), self._make_data)
            self.assertEqual(self._make_data_cntr, 1)
        new_stats = self._make_data.cache.stats()
        self.assertGreater(new_stats["hit"], stats["hit"])
        self.assertGreater(new_stats["misses"], stats["misses"])

    def test_get_newer_version_data(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        stats = self._make_data.cache.stats()
        for i in range(10):
            self._version = f"{i}"
            var = self._make_data("test_get_newer_version_data", tstart, tend)
            # var = self.cache.get_data("test_get_newer_version_data", DateTimeRange(tstart, tend), self._make_data,
            #                          version=f"{i}")
            self.assertEqual(self._make_data_cntr, i + 1)
        new_stats = self._make_data.cache.stats()
        self.assertGreater(new_stats["hit"], stats["hit"])
        self.assertGreater(new_stats["misses"], stats["misses"])

    def test_get_same_version_data(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        self._version = "1.1.1"
        for i in range(10):
            var = self._make_data("test_get_same_version_data", tstart, tend)
            # var = self.cache.get_data("test_get_newer_version_data", DateTimeRange(tstart, tend), self._make_data,
            #                          version="1.1.1")
            self.assertEqual(self._make_data_cntr, 1)

    def test_list_keys(self):
        keys = self._make_data.cache.keys()
        types = [type(key) for key in keys]
        self.assertGreater(len(keys), 0)
        self.assertListEqual(types, [str] * len(types))

    def test_global_keys(self, cache=cache):
        self.assertIsNone(cache.get("Not In Cache"))
        cache.set("In Cache", True)
        self.assertTrue(cache.get("In Cache"))

    def tearDown(self):
        pass

@ddt
class _CacheVersionTest(unittest.TestCase):

    @data(
        ("1.1.1", "1.1.1", operator.eq),
        ("1.1.1", "1.1.2", operator.lt),
        ("1.1.1", "1.1.0", operator.gt),
        ("1", "1.0.0", operator.eq),
        ("1.1", "1.1.2", operator.lt),
        ("1.1.1", "1.1", operator.gt),
        ("1.1", "1.1", operator.eq),
        ("1.1", "1.2", operator.lt),
        ("1.1", "1.0", operator.gt),
        ("1", "1", operator.eq),
        ("1", "2", operator.lt),
        ("1", "0", operator.gt),
        ("2019-09-01T20:17:57Z", "2019-09-01T20:17:57Z", operator.eq),
        ("2019-09-01T20:17:57Z", "2019-09-01T21:17:57Z", operator.lt),
        ("2019-09-01T22:17:57Z", "2019-09-01T20:17:57Z", operator.gt)
    )
    @unpack
    def test_compare_version(self, lhs, rhs, op):
        self.assertTrue(op(str_to_version(lhs), str_to_version(rhs)))

    @data(
        ('1.2.3', Version.parse),
        ("2019-09-01T20:17:57Z", dt_parser.parse),
        ('-', lambda x: None)
    )
    @unpack
    def test_conversion(self, version_str, op):
        self.assertEqual(op(version_to_str(str_to_version(version_str))), op(version_str))


if __name__ == '__main__':
    unittest.main()

del cache
shutil.rmtree(dirpath)
