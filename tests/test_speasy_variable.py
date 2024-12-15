#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `SpeasyVariable` class."""

import unittest

import astropy.table
import astropy.units
import numpy as np
import pandas as pds
from ddt import data, ddt, unpack

from speasy.core import epoch_to_datetime64
from speasy.products.variable import (DataContainer, SpeasyVariable,
                                      VariableAxis, VariableTimeAxis,
                                      from_dataframe, from_dictionary, merge,
                                      to_dataframe, to_dictionary)


def epoch_to_datetime64_s(epoch):
    return np.datetime64(int(epoch * 1e9), 'ns')


def make_simple_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., meta=None,
                    dtype=np.float64):
    time = np.arange(start, stop, step)
    values = time * coef
    values = values.astype(dtype)
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(time))],
                          values=DataContainer(values=values, is_time_dependent=True, meta=meta), columns=["Values"])


def make_simple_var_2cols(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., meta=None):
    time = np.arange(start, stop, step)
    values = np.random.random((len(time), 2))
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(time))],
                          values=DataContainer(values=values, is_time_dependent=True, meta=meta), columns=["x", "y"])


def make_simple_var_3cols(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., meta=None):
    time = np.arange(start, stop, step)
    values = np.random.random((len(time), 3))
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(time))],
                          values=DataContainer(values=values, is_time_dependent=True, meta=meta),
                          columns=["x", "y", "z"])


def make_2d_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., height: int = 32):
    time = np.arange(start, stop, step)
    values = (time * coef).reshape(-1, 1) * np.arange(height).reshape(1, -1)
    y = values * 0.1
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=epoch_to_datetime64(time)),
              VariableAxis(name='y', values=y, is_time_dependent=True)],
        values=DataContainer(values, is_time_dependent=True, meta={"DISPLAY_TYPE": "spectrogram"}), columns=["Values"])


def make_3d_var(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., height: int = 32,
                depth: int = 32):
    time = np.arange(start, stop, step)
    values = np.random.random((len(time), height, depth))
    y = np.repeat(np.arange(height), len(time), axis=0)
    z = np.repeat(np.arange(depth), len(time), axis=0)
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=epoch_to_datetime64(time)),
              VariableAxis(name='y', values=y, is_time_dependent=True),
              VariableAxis(name='z', values=z, is_time_dependent=True)
              ],
        values=DataContainer(values, is_time_dependent=True, meta={"DISPLAY_TYPE": "spectrogram"}), columns=["Values"])


def make_2d_var_1d_y(start: float = 0., stop: float = 0., step: float = 1., coef: float = 1., height: int = 32):
    time = np.arange(start, stop, step)
    values = (time * coef).reshape(-1, 1) * np.arange(height).reshape(1, -1)
    y = np.arange(height)
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=epoch_to_datetime64(
            time)), VariableAxis(name='y', values=y)],
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
        self.assertListEqual(var[2:4].values.squeeze(
        ).tolist(), ref.values.squeeze().tolist())
        ref = ctor(1., 5.)
        self.assertListEqual(var[:4].values.squeeze(
        ).tolist(), ref.values.squeeze().tolist())
        ref = ctor(3., 10.)
        self.assertListEqual(var[2:].values.squeeze(
        ).tolist(), ref.values.squeeze().tolist())

    @data(
        make_simple_var,
        make_2d_var,
        make_2d_var_1d_y
    )
    def test_with_epoch(self, ctor):
        var = ctor(1., 10.)
        ref = ctor(2., 4.)
        self.assertListEqual(var[2.:4.].values.squeeze(
        ).tolist(), ref.values.squeeze().tolist())
        ref = ctor(1., 4.)
        self.assertListEqual(var[:4.].values.squeeze(
        ).tolist(), ref.values.squeeze().tolist())
        ref = ctor(2., 10.)
        self.assertListEqual(var[2.:].values.squeeze(
        ).tolist(), ref.values.squeeze().tolist())

    @data(
        make_simple_var,
        make_2d_var,
        make_2d_var_1d_y
    )
    def test_with_dt64(self, ctor):
        var = ctor(1., 10.)
        ref = ctor(2., 4.)
        self.assertListEqual(var[epoch_to_datetime64_s(2.):epoch_to_datetime64_s(
            4.)].values.squeeze().tolist(), ref.values.squeeze().tolist())
        ref = ctor(1., 4.)
        self.assertListEqual(var[:epoch_to_datetime64_s(
            4.)].values.squeeze().tolist(), ref.values.squeeze().tolist())
        ref = ctor(2., 10.)
        self.assertListEqual(var[epoch_to_datetime64_s(
            2.):].values.squeeze().tolist(), ref.values.squeeze().tolist())

    def test_view_should_modify_it_source(self):
        var = make_simple_var(1., 10., 1., 1.)
        var[:].values[1] = 999.
        self.assertEqual(var.values[1], 999.)

    def test_view_preserves_columns(self):
        var = make_simple_var(1., 10., 1., 1.)
        self.assertEqual(var[:].columns, var.columns)

    def test_can_slice_columns(self):
        var = make_simple_var_2cols(1., 10., 1., 1.)
        x = var["x"]
        y = var["y"]
        cp = var[["x", "y"]]
        cp2 = var["x", "y"]
        self.assertEqual(cp.columns, var.columns)
        self.assertEqual(cp2.columns, var.columns)
        self.assertTrue(np.all(cp.values == var.values))
        self.assertTrue(np.all(cp2.values == var.values))
        self.assertTrue(np.all(cp.axes == var.axes))
        self.assertTrue(np.all(cp2.axes == var.axes))
        self.assertTrue(np.all(x.values[:, 0] == var.values[:, 0]))
        self.assertTrue(np.all(x.axes == var.axes))
        self.assertTrue(np.all(y.values[:, 0] == var.values[:, 1]))
        self.assertTrue(np.all(y.axes == var.axes))

    def test_can_slice_with_numpy_comparison(self):
        var = make_simple_var(1., 10., 1., 1.)
        sliced = var[var > 5]
        self.assertEqual(len(sliced), 4)
        self.assertTrue(np.all(sliced.values > 5))

    def test_can_set_values_where_condition_is_true(self):
        var = make_simple_var(1., 10., 1., 1.)
        var[var < 5] = np.nan
        self.assertTrue(np.all(np.isnan(var.values[:4])))
        self.assertTrue(not np.any(np.isnan(var.values[4:])))


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
        self.assertListEqual(
            var.time.tolist(), make_simple_var().time.tolist())

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
        self.assertListEqual(
            var.time.tolist(), var1.time.tolist() + var2.time.tolist())


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
        var3 = from_dictionary(to_dictionary(var1, array_to_list=True))
        self.assertEqual(var1, var2)
        self.assertEqual(var1, var3)

    def test_from_dict_preserves_dtype(self):
        for dtype in (np.float32, np.float64, np.int32, np.int64):
            var = make_simple_var(1., 10., 1., 10., dtype=dtype)
            var2 = from_dictionary(to_dictionary(var))
            self.assertEqual(var.values.dtype, dtype)
            self.assertEqual(var.values.dtype, var2.values.dtype)

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
            var = make_2d_var(1., 10., 1., 10., 128)
            ax = var.plot()
            self.assertIsNotNone(ax)
        except ImportError:
            self.skipTest("Can't import matplotlib")

    def test_overrides_plot_arguments(self):
        try:
            import matplotlib.pyplot as plt
            var = make_simple_var(1., 10., 1., 10.)
            ax = var.plot(xaxis_label="Time", yaxis_label="Values", units="nT", labels=["Values"])
            self.assertIsNotNone(ax)
            self.assertEqual(ax.get_xlabel(), "Time")
            self.assertEqual(ax.get_ylabel(), "Values (nT)")

            var = make_2d_var(1., 10., 1., 10., 128)
            ax = var.plot(xaxis_label="Time", yaxis_label="Values", yaxis_units="nT", zaxis_label="Values",
                          zaxis_units="nT")
            self.assertIsNotNone(ax)

        except ImportError:
            self.skipTest("Can't import matplotlib")

    def test_replaces_fill_value(self):
        var = make_simple_var(1., 10., 1., 10., meta={"FILLVAL": 50.})
        self.assertEqual(var.fill_value, 50.)
        cleaned_copy = var.replace_fillval_by_nan(inplace=False)
        self.assertTrue(np.isnan(cleaned_copy.values[4, 0]))
        self.assertFalse(np.isnan(var.values[4, 0]))
        var.replace_fillval_by_nan(inplace=True)
        self.assertTrue(np.isnan(var.values[4, 0]))

    def test_clamps(self):
        var = make_simple_var(1., 10., 1., 10., meta={"VALIDMIN": 20., "VALIDMAX": 80.})
        clamped_copy = var.clamp_with_nan()
        self.assertTrue(np.all(np.isnan(clamped_copy.values[0:1, 0])))
        self.assertTrue(np.all(np.isnan(clamped_copy.values[8:10, 0])))
        self.assertFalse(np.any(np.isnan(clamped_copy.values[1:8, 0])))
        var.clamp_with_nan(inplace=True)
        self.assertTrue(np.all(np.isnan(var.values[0:1, 0])))
        self.assertTrue(np.all(np.isnan(var.values[8:10, 0])))
        self.assertFalse(np.any(np.isnan(var.values[1:8, 0])))

    def test_cleans(self):
        var = make_simple_var(1., 10., 1., 10., meta={"FILLVAL": 50., "VALIDMIN": 20., "VALIDMAX": 80.})
        cleaned_copy = var.sanitized()
        self.assertFalse(np.any(np.isnan(cleaned_copy.values)))
        self.assertLess(len(cleaned_copy), len(var))


class TestSpeasyVariableMath(unittest.TestCase):
    def setUp(self):
        self.var = make_simple_var(1., 10., 1., 10.)

    def tearDown(self):
        pass

    def test_addition(self):
        var = self.var + 1
        self.assertTrue(np.all(var.values == self.var.values + 1))

    def test_subtraction(self):
        var = self.var - 1
        self.assertTrue(np.all(var.values == self.var.values - 1))

    def test_multiplication(self):
        var = self.var * 2
        self.assertTrue(np.all(var.values == self.var.values * 2))

    def test_division(self):
        var = self.var / 2
        self.assertTrue(np.all(var.values == self.var.values / 2))

    def test_time_shift(self):
        for shift in (np.timedelta64(1, 'D'), -np.timedelta64(1, 'D')):
            var = self.var + shift
            self.assertTrue(np.all(var.values == self.var.values))
            self.assertTrue(np.all(var.time == self.var.time + shift))


@ddt
class TestSpeasyVariableNumpyInterface(unittest.TestCase):
    def setUp(self):
        self.var = make_simple_var(1., 10., 1., 10.)
        self.vector = make_simple_var_3cols(1., 10., 1., 10.)
        self.spectro = make_2d_var(1., 10., 10., 32)
        self.var3d = make_3d_var(1., 10., 10., 32, 16)

    def tearDown(self):
        pass

    def test_ufunc(self):
        var = np.exp(self.var)
        self.assertTrue(np.all(var.values == np.exp(self.var.values)))

    def test_ufunc_inplace(self):
        values = self.var.values.copy()
        self.var += 1
        self.assertTrue(np.all(self.var.values == values + 1))

    def test_ufunc_inplace_with_output(self):
        out = np.empty_like(self.var)
        np.add(self.var, 1, out=out)
        self.assertTrue(np.all(out.values == self.var.values + 1))

    def test_ufunc_magnitude(self):
        var = np.sqrt(np.sum(np.multiply(self.vector, self.vector), axis=1))
        self.assertTrue(np.allclose(var.values, np.linalg.norm(self.vector.values, axis=1).reshape(-1, 1)))
        self.assertTrue(np.allclose(var, np.linalg.norm(self.vector, axis=1)))

    @data(np.sum, np.mean, np.std, np.var, np.max, np.min)
    def test_functions_that_reduce_ndim_on_axis1(self, func):
        for var in (self.spectro, self.var3d):
            result = func(var, axis=1)
            self.assertEqual(len(var.axes) - 1, len(result.axes))
            self.assertTrue(np.all(result.values == func(var.values, axis=1)))

    @data(np.sum, np.mean, np.std, np.var, np.max, np.min)
    def test_functions_that_reduce_ndim_on_last_axis(self, func):
        for var in (self.spectro, self.var3d):
            axis = len(var.axes) - 1
            result = func(var, axis=axis)
            self.assertEqual(len(var.axes) - 1, len(result.axes))
            self.assertTrue(np.all(result.values == func(var.values, axis=axis)))

    @data(np.sum, np.mean, np.std, np.var, np.max, np.min)
    def test_functions_that_reduce_ndim_on_axis0(self, func):
        for var in (self.spectro, self.var3d):
            result = func(var, axis=0)
            self.assertIsNot(type(result), SpeasyVariable)
            self.assertIsInstance(result, np.ndarray)
            self.assertTrue(np.all(result == func(var.values, axis=0)))

    def test_zeros_like(self):
        var = np.zeros_like(self.var)
        self.assertEqual(self.var.shape, var.shape)
        self.assertEqual(self.var.meta, var.meta)
        self.assertTrue(np.all(var.values == 0))
        self.assertListEqual(self.var.axes, var.axes)
        self.assertListEqual(self.var.columns, var.columns)

    def test_ones_like(self):
        var = np.ones_like(self.var)
        self.assertEqual(self.var.shape, var.shape)
        self.assertEqual(self.var.meta, var.meta)
        self.assertTrue(np.all(var.values == 1))
        self.assertListEqual(self.var.axes, var.axes)
        self.assertListEqual(self.var.columns, var.columns)

    def test_empty_like(self):
        var = np.empty_like(self.var)
        self.assertEqual(self.var.shape, var.shape)
        self.assertEqual(self.var.meta, var.meta)
        self.assertListEqual(self.var.axes, var.axes)
        self.assertListEqual(self.var.columns, var.columns)

    @data(np.sum, np.mean, np.std, np.var, np.max, np.min)
    def test_scalar_result(self, func):
        for v in (self.var, self.vector, self.spectro, self.var3d):
            self.assertIsInstance(func(v), float)


class SpeasyVariableCompare(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


if __name__ == '__main__':
    unittest.main()
