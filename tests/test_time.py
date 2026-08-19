#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.core.time` module."""
import unittest
from datetime import datetime, timezone, timedelta

import numpy as np
from ddt import data, ddt

from speasy.core.time import make_utc_datetime, make_utc_datetime64


@ddt
class MakeUtcDateTime(unittest.TestCase):
    @data(
        'datetime64[D]',
        'datetime64[W]',
        'datetime64[M]',
        'datetime64[s]',
        'datetime64[ms]',
        'datetime64[us]',
        'datetime64[ns]',
    )
    def test_accepts_any_datetime64_unit(self, unit):
        input_dt = np.datetime64('2016-06-02T01:02:03').astype(unit)
        dt = make_utc_datetime(input_dt)
        self.assertEqual(np.datetime64(dt.replace(tzinfo=None), 'ns'),
                         input_dt.astype('datetime64[ns]'))

    def test_accepts_datetime64_beyond_ns_range(self):
        dt = make_utc_datetime(np.datetime64('2500-01-01'))
        self.assertEqual(dt, datetime(2500, 1, 1, tzinfo=timezone.utc))

    def test_converts_tz_aware_datetime_to_utc(self):
        paris = timezone(timedelta(hours=2))
        dt = make_utc_datetime(datetime(2018, 1, 1, 1, 0, tzinfo=paris))
        self.assertEqual(dt, datetime(2017, 12, 31, 23, 0, tzinfo=timezone.utc))

    def test_converts_offset_string_to_utc(self):
        dt = make_utc_datetime("2018-01-01T01:00:00+02:00")
        self.assertEqual(dt, datetime(2017, 12, 31, 23, 0, tzinfo=timezone.utc))

    def test_naive_datetime_is_assumed_utc(self):
        dt = make_utc_datetime(datetime(2020, 1, 1))
        self.assertEqual(dt, datetime(2020, 1, 1, tzinfo=timezone.utc))

    def test_epoch_float(self):
        dt = make_utc_datetime(0.)
        self.assertEqual(dt, datetime(1970, 1, 1, tzinfo=timezone.utc))

    def test_datetime64_ns_sub_microsecond_precision_is_preserved(self):
        # regression test: converting through datetime64[us] would truncate
        # sub-microsecond digits instead of rounding, shifting interval boundaries
        dt = make_utc_datetime(np.datetime64('2016-06-02T01:02:03.123456789'))
        self.assertEqual(dt, datetime(2016, 6, 2, 1, 2, 3, 123457, tzinfo=timezone.utc))


@ddt
class MakeUtcDateTime64(unittest.TestCase):
    @data(
        'datetime64[D]',
        'datetime64[s]',
        'datetime64[ms]',
        'datetime64[us]',
        'datetime64[ns]',
    )
    def test_accepts_any_datetime64_unit(self, unit):
        input_dt = np.datetime64('2016-06-02T01:02:03').astype(unit)
        dt = make_utc_datetime64(input_dt)
        self.assertEqual(dt, input_dt.astype('datetime64[ns]'))

    def test_converts_tz_aware_datetime_to_utc(self):
        paris = timezone(timedelta(hours=2))
        dt = make_utc_datetime64(datetime(2018, 1, 1, 1, 0, tzinfo=paris))
        self.assertEqual(dt, np.datetime64('2017-12-31T23:00:00', 'ns'))

    def test_converts_offset_string_to_utc(self):
        dt = make_utc_datetime64("2018-01-01T01:00:00+02:00")
        self.assertEqual(dt, np.datetime64('2017-12-31T23:00:00', 'ns'))

    def test_epoch_float(self):
        dt = make_utc_datetime64(0.)
        self.assertEqual(dt, np.datetime64('1970-01-01T00:00:00'))

    def test_datetime64_ns_is_returned_unchanged(self):
        dt64 = np.datetime64('2016-06-02T01:02:03.123456789')
        self.assertIs(make_utc_datetime64(dt64), dt64)

    @data(
        np.datetime64('2500-01-01'),
        np.datetime64('1500-01-01'),
        datetime(2500, 1, 1),
        datetime(1500, 1, 1),
        '2500-01-01',
    )
    def test_raises_instead_of_wrapping_outside_the_ns_range(self, input_dt):
        # regression test: numpy wraps around int64 instead of raising, so
        # 2500-01-01 used to silently come back as 1915-06-14T00:25:26.290448384
        with self.assertRaises(ValueError):
            make_utc_datetime64(input_dt)

    @data(
        '1677-09-21T00:12:43.145225',
        '2262-04-11T23:47:16.854775',
    )
    def test_accepts_the_ns_range_boundaries(self, boundary):
        self.assertEqual(make_utc_datetime64(np.datetime64(boundary)),
                         np.datetime64(boundary, 'ns'))


if __name__ == '__main__':
    unittest.main()
