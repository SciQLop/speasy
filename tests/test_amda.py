#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""

import unittest
import os
from datetime import datetime, timezone
import speasy as spz
from speasy.amda import load_csv


class AMDAModule(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_loads_csv(self):
        var = load_csv(f'{os.path.dirname(os.path.abspath(__file__))}/resources/amda_sample_spectro.txt')
        self.assertEqual(var.values.shape[0], len(var.time))
        self.assertEqual(var.values.shape[1], len(var.columns))
        self.assertGreater(len(var.time), 0)
        self.assertTrue('MISSION_ID' in var.meta)


class SimpleRequest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_variable(self):
        start_date = datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result)
        start_date = datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        parameter_id = "c1_hia_prest"
        result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result)

    def test_get_variable_over_midnight(self):
        start_date = datetime(2006, 1, 8, 23, 30, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 9, 0, 30, 0, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = spz.amda.get_parameter(parameter_id, start_date, stop_date, disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result)

    def test_list_parameters(self):
        result = spz.amda.list_parameters()
        self.assertTrue(len(result) != 0)

    def test_get_parameter(self):
        start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)
        r = spz.amda.get_parameter("imf", start, stop, disable_cache=True)
        self.assertIsNotNone(r)

    def test_list_datasets(self):
        result = spz.amda.list_datasets()
        self.assertTrue(len(result) != 0)

    def test_get_dataset(self):
        start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)
        r = spz.amda.get_dataset("tao-ura-sw", start, stop, disable_cache=True)
        self.assertTrue(len(r) != 0)

    def test_list_timetables(self):
        result = spz.amda.list_timetables()
        self.assertTrue(len(result) != 0)

    def test_list_user_timetables(self):
        result = spz.amda.list_user_timetables()
        self.assertTrue(len(result) != 0)

    def test_get_sharedtimeTable_0(self):
        r = spz.amda.get_timetable("sharedtimeTable_0")
        self.assertIsNotNone(r)

    def test_get_timetable_from_TimetableIndex(self):
        r = spz.amda.get_timetable(spz.amda.list_timetables()[-1])
        self.assertIsNotNone(r)


if __name__ == '__main__':
    unittest.main()
