import unittest
from ddt import ddt, data, unpack
from datetime import datetime, timedelta
from .cache import CacheEntry, Cache
from ..common.datetime_range import DateTimeRange
import uuid
import os


class _CacheEntryTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_contains(self):
        start_date = datetime(2006, 1, 8, 1, 0, 0)
        stop_date = start_date + timedelta(hours=1)
        dt_range = DateTimeRange(start_date, stop_date)
        entry = CacheEntry(dt_range, "")
        self.assertTrue((start_date, stop_date) in entry)
        self.assertTrue((start_date + timedelta(minutes=30), stop_date + timedelta(minutes=30)) in entry)
        self.assertTrue((start_date - timedelta(minutes=30), stop_date - timedelta(minutes=30)) in entry)

        self.assertTrue([start_date + timedelta(hours=2), stop_date + timedelta(hours=2)] not in entry)
        with self.assertRaises(ValueError):
            res = (stop_date, start_date) in entry


@ddt
class _CacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = Cache('tmp')
        start_date = datetime(2006, 1, 8, 0, 0, 0)
        stop_date = datetime(2006, 1, 8, 1, 0, 0)
        dt_range = DateTimeRange(start_date, stop_date)
        for i in range(10):
            self.cache.add_entry('product1', CacheEntry(dt_range, f"file{i}"),None)
            dt_range += timedelta(days=1)

        self.cache.add_entry('product1', CacheEntry(dt_range + timedelta(days=2), f"file10"),None)
        self.cache.add_entry('product1', CacheEntry(dt_range + timedelta(days=2,hours=1), f"file10"),None)

    @data(
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 8, 0, 20, 0), datetime(2006, 1, 8, 0, 40, 0)),
                []
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 20, 0, 0, 0), datetime(2006, 1, 20, 2, 0, 0)),
                []
        ),
        (
                'product not in cache',
                DateTimeRange(datetime(2006, 1, 8, 0, 20, 0), datetime(2006, 1, 8, 0, 40, 0)),
                [
                    DateTimeRange(datetime(2006, 1, 8, 0, 20, 0), datetime(2006, 1, 8, 0, 40, 0))
                ]
        ),
        (
                'product1',
                DateTimeRange(datetime(2016, 1, 8, 0, 20, 0), datetime(2016, 1, 8, 0, 40, 0)),
                [
                    DateTimeRange(datetime(2016, 1, 8, 0, 20, 0), datetime(2016, 1, 8, 0, 40, 0))
                ]
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 8, 0, 20, 0), datetime(2006, 1, 8, 1, 40, 0)),
                [
                    DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 1, 40, 0))
                ]
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 7, 23, 20, 0), datetime(2006, 1, 8, 1, 0, 0)),
                [
                    DateTimeRange(datetime(2006, 1, 7, 23, 20, 0), datetime(2006, 1, 8, 0, 0, 0))
                ]
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 7, 23, 20, 0), datetime(2006, 1, 8, 1, 40, 0)),
                [
                    DateTimeRange(datetime(2006, 1, 7, 23, 20, 0), datetime(2006, 1, 8, 0, 0, 0)),
                    DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 8, 1, 40, 0))
                ]
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 9, 1, 40, 0)),
                [
                    DateTimeRange(datetime(2006, 1, 8, 1, 0, 0), datetime(2006, 1, 9, 0, 0, 0)),
                    DateTimeRange(datetime(2006, 1, 9, 1, 0, 0), datetime(2006, 1, 9, 1, 40, 0))
                ]
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 8, 23, 40, 0), datetime(2006, 1, 12, 1, 40, 0)),
                [
                    DateTimeRange(datetime(2006, 1, 8, 23, 40, 0), datetime(2006, 1, 9, 0, 0, 0)),
                    DateTimeRange(datetime(2006, 1, 9, 1, 0, 0), datetime(2006, 1, 10, 0, 0, 0)),
                    DateTimeRange(datetime(2006, 1, 10, 1, 0, 0), datetime(2006, 1, 11, 0, 0, 0)),
                    DateTimeRange(datetime(2006, 1, 11, 1, 0, 0), datetime(2006, 1, 12, 0, 0, 0)),
                    DateTimeRange(datetime(2006, 1, 12, 1, 0, 0), datetime(2006, 1, 12, 1, 40, 0))
                ]
        ),
    )
    @unpack
    def test_get_missing_ranges(self, product, dt_range, expected):
        missing = self.cache.get_missing_ranges(product, dt_range)
        self.assertEqual(expected, missing)

    @data(
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 8, 0, 20, 0), datetime(2006, 1, 8, 0, 40, 0)),
                [
                    CacheEntry(DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)), 'file0')
                ]
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 8, 0, 20, 0), datetime(2006, 1, 9, 0, 40, 0)),
                [
                    CacheEntry(DateTimeRange(datetime(2006, 1, 8, 0, 0, 0), datetime(2006, 1, 8, 1, 0, 0)), 'file0'),
                    CacheEntry(DateTimeRange(datetime(2006, 1, 9, 0, 0, 0), datetime(2006, 1, 9, 1, 0, 0)), 'file1')
                ]
        ),
        (
                'product not in cache',
                DateTimeRange(datetime(2006, 1, 8, 0, 20, 0), datetime(2006, 1, 8, 0, 40, 0)),
                []
        ),
        (
                'product1',
                DateTimeRange(datetime(2006, 1, 8, 1, 0, 1), datetime(2006, 1, 8, 2, 40, 0)),
                []
        )
    )
    @unpack
    def test_get_cache_hit_entries(self, product, dt_range, expected):
        entry = self.cache.get_entries(product, dt_range)
        self.assertEqual(entry, expected)

    def tearDown(self):
        del self.cache


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
        self.assertEquals(
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
