import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.cache.cache import Cache
from spwc.cache import Cacheable, _round_for_cache
from spwc.cache.version import str_to_version
from spwc.common.datetime_range import DateTimeRange
from spwc.common.variable import SpwcVariable
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

    @Cacheable(prefix="", cache_instance=cache, version=version)
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
        for _ in range(10):
            var = self._make_data("test_get_data_more_than_once", tstart,
                                  tend)  # self.cache.get_data("test_get_data_more_than_once", DateTimeRange(tstart, tend), self._make_data)
            self.assertEqual(self._make_data_cntr, 1)

    def test_get_newer_version_data(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        for i in range(10):
            self._version = f"{i}"
            var = self._make_data("test_get_newer_version_data", tstart, tend)
            # var = self.cache.get_data("test_get_newer_version_data", DateTimeRange(tstart, tend), self._make_data,
            #                          version=f"{i}")
            self.assertEqual(self._make_data_cntr, i + 1)

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

    def tearDown(self):
        pass


@ddt
class _DateTimeRangeTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        (
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 3, 0, 0)),
            []
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            []
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)),
                DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 5, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 3, 0, 0))
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 3, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 4, 0, 0))
            ]
        ),
        (
            DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0)),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)),
            [
                DateTimeRange(datetime(2006, 1, 8, 2, 0, 0), datetime(2006, 1, 8, 4, 0, 0))
            ]
        )
    )
    @unpack
    def test_range_diff(self, range1, range2, expected):
        self.assertEqual(range1 - range2, expected)

    def test_range_substract_timedelta(self):
        self.assertEqual(
            DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 2, 0, 0))
            -
            timedelta(hours=1),
            DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)))

    def test_add_with_wrong_type(self):
        with self.assertRaises(TypeError):
            DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 4, 0, 0)) + 1

    def test_substract_with_wrong_type(self):
        with self.assertRaises(TypeError):
            DateTimeRange(datetime(2006, 1, 8, 3, 0, 0), datetime(2006, 1, 8, 4, 0, 0)) - 1

    @data(
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0), datetime(2000, 1, 1, 1, 0, 0)),
            1.,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0), datetime(2000, 1, 1, 1, 0, 0))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 1, 0, 0), datetime(2000, 1, 1, 2, 0, 0)),
            2.,
            DateTimeRange(datetime(2000, 1, 1, 0, 30, 0), datetime(2000, 1, 1, 2, 30, 0))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 30, 0), datetime(2000, 1, 1, 2, 30, 0)),
            .5,
            DateTimeRange(datetime(2000, 1, 1, 1, 0, 0), datetime(2000, 1, 1, 2, 0, 0))
        )
    )
    @unpack
    def test_scale(self, dt_range, factor, expected):
        self.assertEqual(dt_range * factor, expected)

    @data(
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc)),
            1,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 0, 0, 2, tzinfo=timezone.utc)),
            1,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 1, 0, 0, tzinfo=timezone.utc))
        ),
        (
            DateTimeRange(datetime(2000, 1, 1, 3, 30, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 5, 30, 0, tzinfo=timezone.utc)),
            12,
            DateTimeRange(datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                          datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        ),
    )
    @unpack
    def test_range_rounding(self, dt_range, fragment_hours, expected):
        self.assertEqual(_round_for_cache(dt_range, fragment_hours), expected)


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


if __name__ == '__main__':
    unittest.main()

del cache
shutil.rmtree(dirpath)
