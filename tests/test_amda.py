#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""

import unittest
from typing import List
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.amda import AMDA

import tempfile
import shutil
from multiprocessing import dummy


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
