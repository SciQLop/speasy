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
        variables = [make_var(5), make_var(5, columns=("bx",), start=5.)]
        with self.assertRaisesRegex(ValueError, r"same shape.*\(1,\).*\(3,\)"):
            merge(variables)

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


@ddt
class JoiningFunctions(unittest.TestCase):
    @data(np.concatenate, np.vstack, np.hstack, np.stack)
    def test_point_to_merge_instead_of_recursing(self, func):
        v = make_var()
        with self.assertRaisesRegex(TypeError, r"merge\(\)"):
            func([v, v])

    def test_other_functions_taking_a_list_of_variables_do_not_recurse(self):
        v = make_var()
        res = np.select([v.values > 0], [v])
        np.testing.assert_array_equal(res.values, np.select([v.values > 0], [v.values]))
        self.assertTrue(res.name.endswith(", [b])"))


class IndexingByPositionAndName(unittest.TestCase):
    def setUp(self):
        self.v = make_var()

    def test_int_selects_one_row(self):
        row = self.v[2]
        self.assertIsInstance(row, SpeasyVariable)
        self.assertEqual(row.shape, (1, 3))
        np.testing.assert_array_equal(row.values, self.v.values[2:3])
        self.assertEqual(row.time[0], self.v.time[2])

    def test_negative_int_selects_from_the_end(self):
        np.testing.assert_array_equal(self.v[-1].values, self.v.values[-1:])
        np.testing.assert_array_equal(self.v[np.int64(-2)].values, self.v.values[-2:-1])

    def test_out_of_range_int_raises_index_error(self):
        with self.assertRaisesRegex(IndexError, "10 rows"):
            self.v[10]

    def test_unknown_column_raises_key_error_listing_columns(self):
        with self.assertRaisesRegex(KeyError, r"nope.*\['bx', 'by', 'bz'\]"):
            self.v["nope"]
        with self.assertRaisesRegex(KeyError, r"nope.*\['bx', 'by', 'bz'\]"):
            self.v[["bx", "nope"]]

    def test_unsupported_key_says_what_is_supported(self):
        with self.assertRaisesRegex(ValueError, "slice.*column name.*boolean mask"):
            self.v[:, 0]


class UfuncOutParameter(unittest.TestCase):
    def test_returns_the_output_variable(self):
        v = make_var()
        w = v.copy()
        self.assertIs(np.add(v, 1, out=w), w)
        np.testing.assert_array_equal(w.values, v.values + 1)

    def test_extra_keyword_arguments_are_forwarded(self):
        v = make_var()
        w = v.copy()
        mask = v.values > 0
        np.add(v, 1, out=w, where=mask)
        np.testing.assert_array_equal(w.values, np.where(mask, v.values + 1, v.values))


@ddt
class ShapePreservingFunctionsAlongTime(unittest.TestCase):
    @data(np.cumsum, np.sort, np.gradient)
    def test_keep_the_time_axis(self, func):
        v = make_var()
        res = func(v, axis=0)
        self.assertIsInstance(res, SpeasyVariable)
        np.testing.assert_array_equal(res.values, func(v.values, axis=0))
        np.testing.assert_array_equal(res.time, v.time)

    def test_reductions_along_time_still_give_plain_arrays(self):
        square = make_var(n=3)
        self.assertNotIsInstance(np.mean(square, axis=0), SpeasyVariable)
        self.assertEqual(np.mean(square, axis=0).shape, (3,))
        self.assertNotIsInstance(np.diff(square, axis=0), SpeasyVariable)


class DataFrameRoundTrip(unittest.TestCase):
    def test_keeps_name_unit_and_meta(self):
        v = make_var()
        back = SpeasyVariable.from_dataframe(v.to_dataframe())
        self.assertEqual(back.name, "b")
        self.assertEqual(back.unit, "nT")
        self.assertEqual(back, v)

    def test_explicit_arguments_win(self):
        back = SpeasyVariable.from_dataframe(make_var().to_dataframe(), meta={"UNITS": "V"}, name="e")
        self.assertEqual((back.name, back.unit), ("e", "V"))

    def test_plain_dataframe_still_gets_defaults(self):
        df = pds.DataFrame({"a": [1., 2.]}, index=pds.to_datetime(["2020-01-01", "2020-01-02"]))
        back = SpeasyVariable.from_dataframe(df)
        self.assertEqual((back.name, back.meta), ("Unknown", {}))

    def test_concatenating_frames_with_array_meta_still_works(self):
        v = make_var(meta={"UNITS": "nT", "VALIDMIN": np.array([-1., -1., -1.])})
        self.assertEqual(len(pds.concat([v.to_dataframe(), v.to_dataframe()])), 20)

    def test_variable_without_column_names_raises_a_clear_error(self):
        variable = make_spectro_without_columns()
        with self.assertRaisesRegex(ValueError, "0 column names for 3 columns.*with_labels"):
            variable.to_dataframe()

    def test_3d_variable_error_has_no_typo(self):
        time = epoch_to_datetime64(np.arange(2, dtype=float))
        var = SpeasyVariable(axes=[VariableTimeAxis(values=time), VariableAxis(name="y", values=np.arange(2.)),
                                   VariableAxis(name="z", values=np.arange(2.))],
                             values=DataContainer(values=np.ones((2, 2, 2))))
        with self.assertRaisesRegex(ValueError, "^Can't convert"):
            var.to_dataframe()

    def test_empty_dataframe_raises_the_index_error_message(self):
        with self.assertRaisesRegex(ValueError, "index.*datetime"):
            SpeasyVariable.from_dataframe(pds.DataFrame({"a": []}))


class UnitApplied(unittest.TestCase):
    def test_variable_without_unit_becomes_dimensionless(self):
        v = make_var(meta={})
        self.assertEqual(v.unit_applied().values.unit, astropy.units.dimensionless_unscaled)


@ddt
class NaNOnIntegerData(unittest.TestCase):
    def make_int_var(self):
        return make_var(meta={"FILLVAL": -3, "VALIDMIN": -2, "VALIDMAX": 20}, dtype=np.int32)

    @data("replace_fillval_by_nan", "clamp_with_nan")
    def test_error_says_to_convert_to_float(self, method):
        clean = getattr(self.make_int_var(), method)
        with self.assertRaisesRegex(ValueError, "convert_to_float=True"):
            clean()

    @data("replace_fillval_by_nan", "clamp_with_nan")
    def test_convert_to_float_works(self, method):
        self.assertTrue(np.isnan(getattr(self.make_int_var(), method)(convert_to_float=True).values).any())

    @data("replace_fillval_by_nan", "clamp_with_nan")
    def test_int_data_with_nothing_to_replace_is_left_alone(self, method):
        v = make_var(meta={"FILLVAL": -99, "VALIDMIN": -99, "VALIDMAX": 99}, dtype=np.int32)
        np.testing.assert_array_equal(getattr(v, method)().values, v.values)


class PlainRepr(unittest.TestCase):
    def test_repr_describes_the_variable(self):
        text = repr(make_var())
        for expected in ("SpeasyVariable(", "Name: b", "Time Range:", "Shape: (10, 3)", "Unit: nT",
                         "Columns: ['bx', 'by', 'bz']", "Size:"):
            self.assertIn(expected, text)
        self.assertEqual(str(make_var()), text)


class CatalogAppendError(unittest.TestCase):
    def test_names_the_offending_type(self):
        catalog = Catalog(name="c", events=[])
        with self.assertRaisesRegex(TypeError, "str"):
            catalog.append("x")
        events = [Event("2020-01-01", "2020-01-02"), 3]
        with self.assertRaisesRegex(TypeError, "int"):
            catalog.append(events)


class ColormapOfVector(unittest.TestCase):
    def test_raises_a_clear_error(self):
        plot = make_var().plot
        with self.assertRaisesRegex(ValueError, r"plot\.line\(\)"):
            plot.colormap()


if __name__ == '__main__':
    unittest.main()
