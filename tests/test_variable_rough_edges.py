"""Rough edges of SpeasyVariable found by a monkey-test run: clear errors and numpy/pandas interop."""

import unittest

import astropy.units
import numpy as np
import pandas as pds
from ddt import data, ddt

from speasy.core import epoch_to_datetime64
from speasy.products.catalog import Catalog, Event
from speasy.products.variable import (DataContainer, SpeasyVariable, VariableAxis, VariableTimeAxis, merge)


def make_var(n=10, columns=("bx", "by", "bz"), start=0., meta=None, dtype=np.float64):
    time = epoch_to_datetime64(np.arange(start, start + n, 1.))
    values = np.arange(n * len(columns)).reshape(n, len(columns)).astype(dtype) - 3
    return SpeasyVariable(axes=[VariableTimeAxis(values=time, meta={"UNITS": "s"})],
                          values=DataContainer(values=values, name="b", is_time_dependent=True,
                                               meta={"UNITS": "nT"} if meta is None else meta),
                          columns=list(columns))


def make_spectro_without_columns(n=4, height=3):
    time = epoch_to_datetime64(np.arange(n, dtype=float))
    return SpeasyVariable(axes=[VariableTimeAxis(values=time),
                                VariableAxis(name="energy", values=np.arange(height, dtype=float))],
                          values=DataContainer(values=np.ones((n, height)), name="flux", is_time_dependent=True),
                          columns=[])


class MergeShapes(unittest.TestCase):
    def test_refuses_variables_with_different_column_counts(self):
        with self.assertRaisesRegex(ValueError, r"same shape.*\(1,\).*\(3,\)"):
            merge([make_var(5), make_var(5, columns=("bx",), start=5.)])

    def test_still_merges_same_shape_variables(self):
        self.assertEqual(len(merge([make_var(5), make_var(5, start=5.)])), 10)


class UnaryOperators(unittest.TestCase):
    def setUp(self):
        self.v = make_var()

    def test_negative(self):
        self.assertIsInstance(-self.v, SpeasyVariable)
        np.testing.assert_array_equal((-self.v).values, -self.v.values)

    def test_positive(self):
        np.testing.assert_array_equal((+self.v).values, self.v.values)

    def test_abs(self):
        self.assertIsInstance(abs(self.v), SpeasyVariable)
        np.testing.assert_array_equal(abs(self.v).values, np.abs(self.v.values))


if __name__ == '__main__':
    unittest.main()
