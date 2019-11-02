import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.cache.cache import Cache, _round_for_cache
from spwc.cache.version import str_to_version, version_to_str
from spwc.common.datetime_range import DateTimeRange
from spwc.common.variable import SpwcVariable
import operator
import numpy as np

import tempfile
import shutil


class _CacheTest(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.cache = Cache(self.dirpath)
        self._make_data_cntr = 0

    def _make_data(self, tstart, tend):
        index = np.array(
            [(tstart + timedelta(minutes=delta)).timestamp() for delta in range(int((tend - tstart).seconds / 60))])
        data = index / 3600.
        self._make_data_cntr += 1
        return SpwcVariable(time=index, data=data)

    def _get_and_check(self,start,stop):
        var = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(start, stop), self._make_data)
        self.assertIsNotNone(var)
        test = start.timestamp()
        self.assertEqual(var.time[0], start.timestamp())
        self.assertEqual(var.time[-1], (stop - timedelta(minutes=1)).timestamp())
        self.assertEqual(len(var), (stop-start).seconds/60)

    def test_get_less_than_one_hour(self):
        tstart = datetime(2016, 6, 1, 13, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 1, 13, 10, tzinfo=timezone.utc)
        self._get_and_check(tstart,tend)

    def test_get_more_than_one_hour(self):
        tstart = datetime(2016, 6, 1, 13, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 1, 14, 10, tzinfo=timezone.utc)
        self._get_and_check(tstart,tend)

    def test_get_over_midnight(self):
        tstart = datetime(2016, 6, 1, 23, 30, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 2, 0, 30, tzinfo=timezone.utc)
        self._get_and_check(tstart,tend)

    def test_get_data_more_than_once(self):
        tstart = datetime(2010, 6, 1, 12, 0, tzinfo=timezone.utc)
        tend = datetime(2010, 6, 1, 15, 30, tzinfo=timezone.utc)
        self.assertEqual(self._make_data_cntr, 0)
        for _ in range(10):
            var = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(tstart, tend), self._make_data)
            self.assertEqual(self._make_data_cntr,1)

    def tearDown(self):
        del self.cache
        shutil.rmtree(self.dirpath)


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
        ),
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
