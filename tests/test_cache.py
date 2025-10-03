import operator
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
import dateutil.parser as dt_parser
import numpy as np
import packaging.version as Version
from ddt import data, ddt, unpack

from speasy.core import epoch_to_datetime64
from speasy.core.cache import Cache, Cacheable, UnversionedProviderCache, drop_matching_entries
from speasy.core.cache.version import str_to_version, version_to_str
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableTimeAxis)

start_date = datetime(2016, 6, 1, 12, tzinfo=timezone.utc)

dirpath = tempfile.mkdtemp()
cache = Cache(dirpath)

def data_generator(start_time, stop_time):
    index = np.array(
        [(start_time + timedelta(minutes=delta)).timestamp() for delta in
         range(int((stop_time - start_time).seconds / 60))])
    data = index / 3600.
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=epoch_to_datetime64(index))],
        values=DataContainer(values=data))


@ddt
class _CacheTest(unittest.TestCase):
    def setUp(self):
        self._make_data_cntr = 0
        self._make_unversioned_data_cntr = 0
        self._version = 0

    def version(self, product):
        return self._version

    @Cacheable(prefix="", cache_instance=cache, version=version, leak_cache=True)
    def _make_data(self, product, start_time, stop_time):
        self._make_data_cntr += 1
        return data_generator(start_time, stop_time)

    @UnversionedProviderCache(prefix="", cache_instance=cache, leak_cache=True,
                              cache_retention=timedelta(microseconds=5e5))
    def _make_unversioned_data(self, product, start_time, stop_time, if_newer_than=None):
        if if_newer_than is None or (if_newer_than + timedelta(seconds=1)) < datetime.now(tz=timezone.utc):
            self._make_unversioned_data_cntr += 1
            return data_generator(start_time, stop_time)
        return None

    def _get_and_check(self, start, stop, data_f):
        var = data_f(f"...{data_f}", start, stop)
        self.assertIsNotNone(var)
        self.assertEqual(var.time[0], np.datetime64(start, 'ns'))
        self.assertEqual(var.time[-1], np.datetime64(stop - timedelta(minutes=1), 'ns'))
        self.assertEqual(len(var), (stop - start).seconds / 60)

    def test_get_data_unversioned_prefer_cache(self):
        self._make_unversioned_data_cntr = 0
        var = self._make_unversioned_data("test_get_data_unversioned_prefer_cache", start_date,
                                          start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_unversioned_data_cntr, 1)
        time.sleep(1)
        var = self._make_unversioned_data("test_get_data_unversioned_prefer_cache", start_date,
                                          start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_unversioned_data_cntr, 2)
        var = self._make_unversioned_data("test_get_data_unversioned_prefer_cache", start_date,
                                          start_date + timedelta(minutes=10), prefer_cache=True)
        self.assertIsNotNone(var)
        self.assertEqual(self._make_unversioned_data_cntr, 2)

    def test_get_data_prefer_cache(self):
        self._make_data_cntr = 0
        self._version = "1.0.0"
        var = self._make_data("test_get_data_prefer_cache", start_date, start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_data_cntr, 1)
        self._version = "1.0.1"
        var = self._make_data("test_get_data_prefer_cache", start_date, start_date + timedelta(minutes=10))
        self.assertIsNotNone(var)
        self.assertEqual(self._make_data_cntr, 2)
        self._version = "1.0.2"
        var = self._make_data("test_get_data_prefer_cache", start_date, start_date + timedelta(minutes=10),
                              prefer_cache=True)
        self.assertIsNotNone(var)
        self.assertEqual(self._make_data_cntr, 2)

    @data(
        (start_date, start_date + timedelta(minutes=10), "Less than one hour"),
        (start_date, start_date + timedelta(minutes=70), "More than one hour"),
        (start_date, start_date + timedelta(hours=13), "Over midnight")
    )
    @unpack
    def test_get_data(self, tstart, tend, name):
        self._get_and_check(tstart, tend, self._make_data)
        self._get_and_check(tstart, tend, self._make_unversioned_data)

    def test_get_data_more_than_once(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        stats = self._make_data.cache.stats()
        for _ in range(10):
            var = self._make_data("test_get_data_more_than_once", tstart,
                                  tend)
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
            self.assertEqual(self._make_data_cntr, 1)

    def test_get_cached_from_unversioned_cache(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_unversioned_data_cntr, 0)
        for i in range(10):
            var = self._make_unversioned_data("test_get_cached_from_unversioned_cache", tstart, tend)
            self.assertEqual(self._make_unversioned_data_cntr, 1)

    def test_get_outdated_from_unversioned_cache(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_unversioned_data_cntr, 0)
        var = self._make_unversioned_data("test_get_outdated_from_unversioned_cache", tstart, tend)
        time.sleep(3.)
        var = self._make_unversioned_data("test_get_outdated_from_unversioned_cache", tstart, tend)
        self.assertEqual(self._make_unversioned_data_cntr, 2)

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
class CacheRequestsDeduplication(unittest.TestCase):

    def setUp(self):
        self._make_data_cntr = 0
        self._version = 0
        drop_matching_entries(r".*test_deduplication.*")

    def tearDown(self):
        drop_matching_entries(r".*test_deduplication.*")

    def version(self, product):
        return self._version

    @Cacheable(prefix="", version=version)
    def _make_data(self, product, start_time, stop_time):
        self._make_data_cntr += 1
        time.sleep(.001)
        return data_generator(start_time, stop_time)

    @data(*list(range(20)))
    def test_deduplication(self, step):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        from threading import Thread
        threads = [Thread(target=self._make_data, args=("test_deduplication_product", tstart, tend)) for _ in range(5)]
        for p in threads:
            p.start()
        for p in threads:
            p.join()
        self.assertEqual(self._make_data_cntr, 1)


@ddt
class CacheRequestsDeduplicationMultiProcess(unittest.TestCase):

    @staticmethod
    def increase_count():
        from speasy.core.cache import _cache
        _cache._data.incr("test_deduplication_counter", 1, default=0)

    @property
    def count(self):
        from speasy.core.cache import _cache
        return _cache._data.get("test_deduplication_counter", 0)

    def setUp(self):
        self._version = 0
        drop_matching_entries(r".*test_deduplication.*")
        drop_matching_entries(r"test_deduplication_counter")

    def tearDown(self):
        drop_matching_entries(r".*test_deduplication.*")
        drop_matching_entries(r"test_deduplication_counter")

    def version(self, product):
        return self._version

    @Cacheable(prefix="", version=version)
    def _make_data(self, product, start_time, stop_time):
        self.increase_count()
        time.sleep(.001)
        return data_generator(start_time, stop_time)

    @data(*list(range(50)))
    def test_deduplication(self, step):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self.count, 0)
        from multiprocessing import Process
        processes = [Process(target=self._make_data, args=("test_deduplication_product", tstart, tend)) for _ in range(5)]
        for p in processes:
            p.start()
        for p in processes:
            p.join()
        self.assertEqual(self.count, 1)


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

try:
    del cache
    shutil.rmtree(dirpath)
except PermissionError:
    print(f"Can't rm temporary cache folder {dirpath}")
