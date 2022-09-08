#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `SpeasyVariable` class."""

import unittest
from ddt import ddt, data, unpack

from speasy.products.variable import SpeasyVariable, VariableTimeAxis, VariableAxis, DataContainer, merge, to_dataframe, \
    from_dataframe, to_dictionary, from_dictionary
import numpy as np
import pandas as pds

import astropy.table
import astropy.units


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., meta=None):
    time = np.arange(start, stop, step)
    values = time * coef
    return SpeasyVariable(axes=[VariableTimeAxis(values=SpeasyVariable.epoch_to_datetime64(time))],
                          values=DataContainer(values=values, is_time_dependent=True, meta=meta), columns=["Values"])


def make_2d_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., height: int = 32):
    time = np.arange(start, stop, step)
    values = (time * coef).reshape(-1, 1) * np.arange(height).reshape(1, -1)
    y = values * 0.1
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=SpeasyVariable.epoch_to_datetime64(time)),
              VariableAxis(name='y', values=y, is_time_dependent=True)],
        values=DataContainer(values, is_time_dependent=True), columns=["Values"])


def make_2d_var_1d_y(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., height: int = 32):
    time = np.arange(start, stop, step)
    values = (time * coef).reshape(-1, 1) * np.arange(height).reshape(1, -1)
    y = np.arange(height)
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=SpeasyVariable.epoch_to_datetime64(time)), VariableAxis(name='y', values=y)],
        values=DataContainer(values, is_time_dependent=True), columns=["Values"])


@ddt
class SpeasyVariableSlice(unittest.TestCase):
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
class SpeasyVariableMerge(unittest.TestCase):
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
class ASpeasyVariable(unittest.TestCase):
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

    def test_to_dict(self):
        var = make_simple_var(1., 10., 1., 10.)
        d = to_dictionary(var)
        self.assertIs(type(d), dict)
        for attr in ['axes', 'values', 'columns']:
            self.assertIn(attr, d)
        dc_attributes = ['values', 'meta', 'name', 'is_time_dependent']
        for attr in dc_attributes:
            self.assertIn(attr, d['values'])
        for axis in d['axes']:
            for attr in dc_attributes + ['type']:
                self.assertIn(attr, axis)

    def test_from_dict(self):
        var1 = make_simple_var(1., 10., 1., 10.)
        var2 = from_dictionary(to_dictionary(var1))
        self.assertEqual(var1, var2)

    def test_from_dataframe(self):
        var1 = make_simple_var(1., 10., 1., 10.)
        var2 = from_dataframe(to_dataframe(var1))
        self.assertListEqual(var1.time.tolist(), var2.time.tolist())
        self.assertListEqual(var1.values.tolist(), var2.values.tolist())

    @data(
        ({"UNITS": "nT"}, astropy.units.nT),
        ({"PARAMETER_UNITS": "not a unit"}, None),
        ({}, None)
    )
    @unpack
    def test_can_be_converted_to_astropy_table(self, meta, expected):
        var = make_simple_var(1., 10., 1., 10., meta=meta)
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


class SpeasyVariableCompare(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
