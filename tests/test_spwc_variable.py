#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `SpwcVariable` class."""

import unittest
import os
from typing import List
from ddt import ddt, data, unpack
from datetime import datetime, timedelta, timezone
from spwc.common.variable import SpwcVariable, merge, load_csv
from spwc.amda import AMDA
import numpy as np


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1.):
    var = SpwcVariable()
    var.time = np.arange(start, stop, step)
    var.data = var.time * coef
    return var


class SpwcVariableTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_load_csv(self):
        var = load_csv(f'{os.path.dirname(os.path.abspath(__file__))}/resources/amda_sample_spectro.txt')
        self.assertEqual(var.data.shape[0], len(var.time))
        self.assertGreater(len(var.time), 0)
        self.assertTrue('MISSION_ID' in var.meta)


class SpwcVariableMerge(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_drops_empty(self):
        merge([make_simple_var(), make_simple_var()])

    def test_two_identical(self):
        var1 = make_simple_var(1.,4.,1.,10.)
        var2 = make_simple_var(1.,4.,1.,10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), np.arange(1., 4., 1.).tolist())

    def test_two_with_partial_overlap(self):
        var1 = make_simple_var(1.,10.,1.,10.)
        var2 = make_simple_var(5.,15.,1.,10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), np.arange(1.,15.,1.).tolist())

    def test_two_without_overlap(self):
        var1 = make_simple_var(1.,10.,1.,10.)
        var2 = make_simple_var(10.,20.,1.,10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), np.arange(1., 20., 1.).tolist())
