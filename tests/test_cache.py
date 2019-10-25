import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.cache.cache import Cache, _round_for_cache
from spwc.common.datetime_range import DateTimeRange
from spwc.common.variable import SpwcVariable
import numpy as np

import tempfile
import shutil


class _CacheTest(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.cache = Cache(self.dirpath)

    def _make_data(self, tstart, tend):
        index = np.array(
            [(tstart + timedelta(minutes=delta)).timestamp() for delta in range(int((tend - tstart).seconds / 60))])
        data = index / 3600.
        return SpwcVariable(time=index, data=data)

    def test_get_less_than_one_hour(self):
        tstart = datetime(2016, 6, 1, 13, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 1, 13, 10, tzinfo=timezone.utc)
        var = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(tstart, tend), self._make_data)
        self.assertIsNotNone(var)
        test = tstart.timestamp()
        self.assertEqual(var.time[0], tstart.timestamp())
        self.assertEqual(var.time[-1], (tend - timedelta(minutes=1)).timestamp())
        self.assertEqual(len(var), 10)

    def test_get_more_than_one_hour(self):
        tstart = datetime(2016, 6, 1, 13, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 1, 14, 10, tzinfo=timezone.utc)
        var = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(tstart, tend), self._make_data)
        self.assertIsNotNone(var)
        self.assertEqual(var.time[0], tstart.timestamp())
        self.assertEqual(var.time[-1], (tend - timedelta(minutes=1)).timestamp())
        self.assertEqual(len(var), 70)

    def test_get_over_midnight(self):
        tstart = datetime(2016, 6, 1, 23, 30, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 2, 0, 30, tzinfo=timezone.utc)
        var = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(tstart, tend), self._make_data)
        self.assertIsNotNone(var)
        self.assertEqual(var.time[0], tstart.timestamp())
        self.assertEqual(var.time[-1], (tend - timedelta(minutes=1)).timestamp())
        self.assertEqual(len(var), 60)

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
