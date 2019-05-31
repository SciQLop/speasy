#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""

import unittest
import os
from typing import List
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.amda import AMDA,load_csv

import tempfile
import shutil
from multiprocessing import dummy

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

class simple_request(unittest.TestCase):
    def setUp(self):
        self.ws = AMDA()

    def tearDown(self):
        pass

    def test_get_variable(self):
        start_date = datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 8, 1, 0, 1, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = self.ws.get_parameter(start_date, stop_date, parameter_id, method="REST")
        self.assertIsNotNone(result)
        start_date = datetime(2016, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        stop_date = datetime(2016, 1, 8, 1, 0, 1, tzinfo=timezone.utc)
        parameter_id = "c1_hia_prest"
        result = self.ws.get_parameter(start_date, stop_date, parameter_id, method="REST")
        self.assertIsNotNone(result)

    def test_get_variable_over_midnight(self):
        start_date = datetime(2006, 1, 8, 23, 30, 0, tzinfo=timezone.utc)
        stop_date = datetime(2006, 1, 9, 0, 30, 0, tzinfo=timezone.utc)
        parameter_id = "c1_b_gsm"
        result = self.ws.get_parameter(start_date, stop_date, parameter_id, method="REST")
        self.assertIsNotNone(result)
