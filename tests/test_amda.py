#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""

import unittest
import os
from datetime import datetime, timezone
from speasy.amda import AMDA, load_csv
from ddt import ddt, data


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


@ddt
class SimpleRequest(unittest.TestCase):
    def setUp(self):
        self.ws = AMDA()

    def tearDown(self):
        pass

    @data("REST", "SOAP")
    def test_get_variable(self, method):
        start_date = datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = self.ws.get_parameter(parameter_id, start_date, stop_date, method=method, disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result)
        start_date = datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2016, 1, 8, 1, 0, 10, tzinfo=timezone.utc)
        parameter_id = "c1_hia_prest"
        result = self.ws.get_parameter(parameter_id, start_date, stop_date, method=method, disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result)

    @data("REST", "SOAP")
    def test_get_variable_over_midnight(self, method):
        start_date = datetime(2006, 1, 8, 23, 30, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 9, 0, 30, 0, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = self.ws.get_parameter(parameter_id, start_date, stop_date, method=method, disable_proxy=True,
                                       disable_cache=True)
        self.assertIsNotNone(result)

    def test_list_parameters(self):
        result = self.ws.list_parameters()
        self.assertTrue(len(result) != 0)

    def test_get_parameter(self):
        start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)
        r = self.ws.get_parameter("imf", start, stop, disable_cache=True)
        self.assertIsNotNone(r)

    def test_list_datasets(self):
        result = self.ws.list_datasets()
        self.assertTrue(len(result) != 0)

    def test_get_dataset(self):
        start, stop = datetime(2000, 1, 1), datetime(2000, 1, 2)
        r = self.ws.get_dataset("tao-ura-sw", start, stop, disable_cache=True)
        self.assertTrue(len(r) != 0)

    def test_list_timetables(self):
        result = self.ws.list_timetables()
        self.assertTrue(len(result) != 0)

    def test_get_timetable(self):
        r = self.ws.get_timetable("sharedtimeTable_0")
        self.assertIsNotNone(r)


if __name__ == '__main__':
    unittest.main()
