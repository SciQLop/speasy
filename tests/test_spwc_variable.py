#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `SpwcVariable` class."""

import unittest
import os
from spwc.common.variable import SpwcVariable, merge, load_csv
import numpy as np


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1.):
    var = SpwcVariable()
    var.time = np.arange(start, stop, step)
    var.data = var.time * coef
    return var


class ASpwcVariable(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_load_csv(self):
        var = load_csv(f'{os.path.dirname(os.path.abspath(__file__))}/resources/amda_sample_spectro.txt')
        self.assertEqual(var.data.shape[0], len(var.time))
        self.assertEqual(var.data.shape[1], len(var.columns))
        self.assertGreater(len(var.time), 0)
        self.assertTrue('MISSION_ID' in var.meta)


class SpwcVariableSlice(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_with_indexes(self):
        var = make_simple_var(1., 10., 1., 1.)
        self.assertListEqual(var[2:4].data.tolist(), np.arange(3., 5.).tolist())
        self.assertListEqual(var[:4].data.tolist(), np.arange(1., 5.).tolist())
        self.assertListEqual(var[2:].data.tolist(), np.arange(3., 10.).tolist())

    def test_with_epoch(self):
        var = make_simple_var(1., 10., 1., 1.)
        self.assertListEqual(var[2.:4.].data.tolist(), np.arange(2., 4.).tolist())
        self.assertListEqual(var[:4.].data.tolist(), np.arange(1., 4.).tolist())
        self.assertListEqual(var[2.:].data.tolist(), np.arange(2., 10.).tolist())

    def test_view_should_modify_it_source(self):
        var = make_simple_var(1., 10., 1., 1.)
        var[:].data[1]=999.
        self.assertEqual(var.data[1],999.)


class SpwcVariableMerge(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_drops_empty(self):
        var = merge([make_simple_var(), make_simple_var()])
        self.assertListEqual(var.time.tolist(), make_simple_var().time.tolist())

    def test_two_identical(self):
        var1 = make_simple_var(1., 4., 1., 10.)
        var2 = make_simple_var(1., 4., 1., 10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), np.arange(1., 4., 1.).tolist())

    def test_two_with_partial_overlap(self):
        var1 = make_simple_var(1., 10., 1., 10.)
        var2 = make_simple_var(5., 15., 1., 10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), np.arange(1., 15., 1.).tolist())

    def test_two_without_overlap(self):
        var1 = make_simple_var(1., 10., 1., 10.)
        var2 = make_simple_var(10., 20., 1., 10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), np.arange(1., 20., 1.).tolist())
