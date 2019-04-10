import unittest
from typing import List
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.cache.cache import Cache
from spwc.common.datetime_range import DateTimeRange
import pandas as pds
import uuid
import os

import tempfile
import shutil


class _CacheTest(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.cache = Cache(self.dirpath)

    def _make_data(self, tstart, tend):
        index = [tstart + timedelta(minutes=delta) for delta in range(int((tend - tstart).seconds / 60))]
        data = [t.hour for t in index]
        return pds.DataFrame(index=index, data=data)

    def test_get_less_than_one_hour(self):
        tstart = datetime(2016, 6, 1, 13, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 1, 13, 10, tzinfo=timezone.utc)
        df = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(tstart, tend), self._make_data)
        self.assertIsNotNone(df)
        self.assertEqual(df.index[0], tstart)
        self.assertEqual(df.index[-1], tend-timedelta(minutes=1))
        self.assertEqual(len(df), 10)

    def test_get_more_than_one_hour(self):
        tstart = datetime(2016, 6, 1, 13, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 1, 14, 10, tzinfo=timezone.utc)
        df = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(tstart, tend), self._make_data)
        self.assertIsNotNone(df)
        self.assertEqual(df.index[0], tstart)
        self.assertEqual(df.index[-1], tend-timedelta(minutes=1))
        self.assertEqual(len(df), 70)

    def test_get_over_midnight(self):
        tstart = datetime(2016, 6, 1, 23,30, tzinfo=timezone.utc)
        tend = datetime(2016, 6, 2, 0, 30, tzinfo=timezone.utc)
        df = self.cache.get_data("test_get_less_than_one_hour", DateTimeRange(tstart, tend), self._make_data)
        self.assertIsNotNone(df)
        self.assertEqual(df.index[0], tstart)
        self.assertEqual(df.index[-1], tend-timedelta(minutes=1))
        self.assertEqual(len(df), 60)

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
