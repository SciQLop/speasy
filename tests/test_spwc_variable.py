#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `SpeasyVariable` class."""

import unittest
from ddt import ddt, data, unpack

from speasy.products.variable import SpeasyVariable, merge, to_dataframe, from_dataframe
import numpy as np
import pandas as pds

import astropy.table
import astropy.units


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1.):
    time = np.arange(start, stop, step)
    values = time * coef
    return SpeasyVariable(time=SpeasyVariable.epoch_to_datetime64(time), data=values, meta=None, columns=["Values"],
                          y=None)


def make_2d_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., height: int = 32):
    time = np.arange(start, stop, step)
    values = (time * coef).reshape(-1, 1) * np.arange(height).reshape(1, -1)
    y = values * 0.1
    return SpeasyVariable(time=SpeasyVariable.epoch_to_datetime64(time), data=values, meta=None, columns=["Values"],
                          y=y)


def make_2d_var_1d_y(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., height: int = 32):
    time = np.arange(start, stop, step)
    values = (time * coef).reshape(-1, 1) * np.arange(height).reshape(1, -1)
    y = np.arange(height)
    return SpeasyVariable(time=SpeasyVariable.epoch_to_datetime64(time), data=values, meta=None, columns=["Values"],
                          y=y)


@ddt
class SpwcVariableSlice(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        make_simple_var,
        make_2d_var,
        make_2d_var_1d_y
    )
    def test_with_indexes(self, ctor):
        var = ctor(1., 10.)
        ref = ctor(3., 5.)
        self.assertListEqual(var[2:4].values.squeeze().tolist(), ref.values.squeeze().tolist())
        ref = ctor(1., 5.)
        self.assertListEqual(var[:4].values.squeeze().tolist(), ref.values.squeeze().tolist())
        ref = ctor(3., 10.)
        self.assertListEqual(var[2:].values.squeeze().tolist(), ref.values.squeeze().tolist())

    @data(
        make_simple_var,
        make_2d_var,
        make_2d_var_1d_y
    )
    def test_with_epoch(self, ctor):
        var = ctor(1., 10.)
        ref = ctor(2., 4.)
        self.assertListEqual(var[2.:4.].values.squeeze().tolist(), ref.values.squeeze().tolist())
        ref = ctor(1., 4.)
        self.assertListEqual(var[:4.].values.squeeze().tolist(), ref.values.squeeze().tolist())
        ref = ctor(2., 10.)
        self.assertListEqual(var[2.:].values.squeeze().tolist(), ref.values.squeeze().tolist())

    def test_view_should_modify_it_source(self):
        var = make_simple_var(1., 10., 1., 1.)
        var[:].values[1] = 999.
        self.assertEqual(var.values[1], 999.)


@ddt
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

    @data(
        make_simple_var,
        make_2d_var,
        make_2d_var_1d_y
    )
    def test_two_identical(self, ctor):
        var1 = ctor(1., 4., 1., 10.)
        var2 = ctor(1., 4., 1., 10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), var1.time.tolist())
        self.assertListEqual(var.time.tolist(), var2.time.tolist())

    @data(
        make_simple_var,
        make_2d_var,
        make_2d_var_1d_y
    )
    def test_two_with_partial_overlap(self, ctor):
        var1 = ctor(1., 10., 1., 10.)
        var2 = ctor(5., 15., 1., 10.)
        ref = ctor(1., 15., 1., 10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), ref.time.tolist())

    @data(
        make_simple_var,
        make_2d_var,
        make_2d_var_1d_y
    )
    def test_two_without_overlap(self, ctor):
        var1 = ctor(1., 10., 1., 10.)
        var2 = ctor(10., 20., 1., 10.)
        var = merge([var1, var2])
        self.assertListEqual(var.time.tolist(), var1.time.tolist() + var2.time.tolist())


@ddt
class ASpwcVariable(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_to_dataframe(self):
        var = make_simple_var(1., 10., 1., 10.)
        df = to_dataframe(var)
        self.assertIs(type(df), pds.DataFrame)
        self.assertIs(type(df.index[0]), pds.Timestamp)
        self.assertEqual(var.values.shape, df.values.shape)

    def test_from_dataframe(self):
        var1 = make_simple_var(1., 10., 1., 10.)
        var2 = from_dataframe(to_dataframe(var1))
        self.assertListEqual(var1.time.tolist(), var2.time.tolist())
        self.assertListEqual(var1.values.tolist(), var2.values.tolist())

    @data(
        ({"PARAMETER_UNITS": "nT"}, astropy.units.nT),
        ({"PARAMETER_UNITS": "not a unit"}, None),
        ({}, None)
    )
    @unpack
    def test_can_be_converted_to_astropy_table(self, meta, expected):
        var = make_simple_var(1., 10., 1., 10.)
        # valid astropy unit
        var.meta = meta
        at = var.to_astropy_table()
        self.assertIsInstance(at, astropy.table.Table)
        self.assertEqual(at["Values"].unit, expected)

    def test_is_plotable(self):
        try:
            import matplotlib.pyplot as plt
            var = make_simple_var(1., 10., 1., 10.)
            ax = var.plot()
            self.assertIsNotNone(ax)
        except ImportError:
            self.skipTest("Can't import matplotlib")


class SpwcVariableCompare(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
