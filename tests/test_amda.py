#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""

import unittest
import os
from datetime import datetime, timezone
from spwc.amda import amda
from spwc.cache import Cache
from spwc.amda import AMDA, load_csv
import tempfile
import shutil
from ddt import ddt, data, unpack


class AMDAModule(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_loads_csv(self):
        var = load_csv(f'{os.path.dirname(os.path.abspath(__file__))}/resources/amda_sample_spectro.txt')
        self.assertEqual(var.data.shape[0], len(var.time))
        self.assertEqual(var.data.shape[1], len(var.columns))
        self.assertGreater(len(var.time), 0)
        self.assertTrue('MISSION_ID' in var.meta)


@ddt
class SimpleRequest(unittest.TestCase):
    def setUp(self):
        self.default_cache_path = amda._cache._data.directory
        self.cache_path = tempfile.mkdtemp()
        amda._cache = Cache(self.cache_path)
        self.ws = AMDA()

    def tearDown(self):
        amda._cache = Cache(self.default_cache_path)
        shutil.rmtree(self.cache_path)

    @data("REST", "SOAP")
    def test_get_variable(self, method):
        start_date = datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 8, 1, 0, 1, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = self.ws.get_parameter(start_date, stop_date, parameter_id, method=method)
        self.assertIsNotNone(result)
        start_date = datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2016, 1, 8, 1, 0, 1, tzinfo=timezone.utc)
        parameter_id = "c1_hia_prest"
        result = self.ws.get_parameter(start_date, stop_date, parameter_id, method=method)
        self.assertIsNotNone(result)

    @data("REST", "SOAP")
    def test_get_variable_over_midnight(self, method):
        start_date = datetime(2006, 1, 8, 23, 30, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 9, 0, 30, 0, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = self.ws.get_parameter(start_date, stop_date, parameter_id, method=method)
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
