#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package."""

import unittest
from typing import List
from ddt import ddt, data, unpack
from datetime import datetime, timedelta
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
        start_date = datetime(2006, 1, 8, 1, 0, 0)
        stop_date = datetime(2006, 1, 8, 1, 0, 1)
        parameter_id = "c1_b_gsm"
        result = self.ws.get_parameter(start_date, stop_date, parameter_id, method="REST")
        self.assertIsNotNone(result)
