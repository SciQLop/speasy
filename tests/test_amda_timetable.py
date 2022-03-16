#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package timetable implementation."""

import unittest
import speasy as spz
from speasy.core.datetime_range import DateTimeRange


class TimetableRequests(unittest.TestCase):
    def setUp(self):
        self.tt = spz.amda.get_timetable("sharedtimeTable_0")

    def tearDown(self):
        pass

    def test_timetable_shape(self):
        self.assertTrue(len(self.tt) > 0)

    def test_timetable_has_a_name(self):
        self.assertIsNot(self.tt.name, "")

    def test_is_convertible_to_dataframe(self):
        df = self.tt.to_dataframe()
        self.assertTrue(len(df) > 0)
        self.assertListEqual(list(df.columns), ['start_time', 'stop_time'])
        df_ranges = list(map(lambda row: DateTimeRange(*row), df.values))
        self.assertListEqual(df_ranges, list(self.tt))


if __name__ == '__main__':
    unittest.main()
