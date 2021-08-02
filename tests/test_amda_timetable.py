#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `amda` package timetable implementation."""

import unittest
import os
from datetime import datetime, timezone
from speasy.amda import AMDA, load_csv
from ddt import ddt, data
import numpy as np


@ddt
class SimpleRequest(unittest.TestCase):
    def setUp(self):
        self.ws = AMDA()
        self.tt = self.ws.get_timetable("sharedtimeTable_0")


    def tearDown(self):
        pass

    def test_timetable_shape(self):
        self.assertTrue(self.tt.time.shape[0]==self.tt.values.shape[0])
    def test_tt_time_array(self):
        self.assertTrue(isinstance(self.tt.time, np.ndarray))
    def test_tt_data_array(self):
        self.assertTrue(isinstance(self.tt.values, np.ndarray))
    def test_tt_time_type(self):
        self.assertTrue(self.tt.time.dtype==np.float64)
    def test_tt_data_type(self):
        self.assertTrue(self.tt.values.dtype==np.float64)




if __name__ == '__main__':
    unittest.main()
