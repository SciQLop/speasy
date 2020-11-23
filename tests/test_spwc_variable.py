#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `SpwcVariable` class."""

import unittest

from spwc.common.variable import SpwcVariable, merge, to_dataframe, from_dataframe
import numpy as np
import pandas as pds


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1.):
    time = np.arange(start, stop, step)
    values = time * coef
    return SpwcVariable(time=time, data=values, meta=None, columns=["Values"], y=None)


class SpwcVariableSlice(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_with_indexes(self):
        var = make_simple_var(1., 10., 1., 1.)
        self.assertListEqual(var[2:4].values.squeeze().tolist(), np.arange(3., 5.).tolist())
        self.assertListEqual(var[:4].values.squeeze().tolist(), np.arange(1., 5.).tolist())
        self.assertListEqual(var[2:].values.squeeze().tolist(), np.arange(3., 10.).tolist())

    def test_with_epoch(self):
        var = make_simple_var(1., 10., 1., 1.)
        self.assertListEqual(var[2.:4.].values.squeeze().tolist(), np.arange(2., 4.).tolist())
        self.assertListEqual(var[:4.].values.squeeze().tolist(), np.arange(1., 4.).tolist())
        self.assertListEqual(var[2.:].values.squeeze().tolist(), np.arange(2., 10.).tolist())

    def test_view_should_modify_it_source(self):
        var = make_simple_var(1., 10., 1., 1.)
        var[:].values[1] = 999.
        self.assertEqual(var.values[1], 999.)


class SpwcVariableMerge(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_empty_list(self):
        self.assertIsNone(merge([]))

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


class ASpwcVariable(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_to_dataframe(self):
        var = make_simple_var(1., 10., 1., 10.)
        df = to_dataframe(var)
        self.assertIs(type(df), pds.DataFrame)
        self.assertIs(type(df.index[0]), np.float64)
        self.assertEqual(var.values.shape, df.values.shape)
        df = to_dataframe(var, datetime_index=True)
        self.assertIs(type(df.index[0]), pds.Timestamp)

    def test_from_dataframe(self):
        var1 = make_simple_var(1., 10., 1., 10.)
        var2 = from_dataframe(to_dataframe(var1))
        self.assertListEqual(var1.time.tolist(), var2.time.tolist())
        self.assertListEqual(var1.values.tolist(), var2.values.tolist())
        var3 = from_dataframe(to_dataframe(var1, datetime_index=True))
        self.assertListEqual(var1.time.tolist(), var3.time.tolist())
        self.assertListEqual(var1.values.tolist(), var3.values.tolist())


class SpwcVariableCompare(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
