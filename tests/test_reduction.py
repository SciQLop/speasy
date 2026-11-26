"""speasy.signal.reduction: dimension, sel and integrate a SpeasyVariable along any axis."""
import unittest

import astropy.units as u
import numpy as np

from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products import SpeasyVariable
from speasy.signal.reduction import dimension, integrate, sel

_T = 3
_TIME = np.arange('2020-01-01', '2020-01-01T00:00:03', np.timedelta64(1, 's'), dtype='datetime64[ns]')
_X = np.array([1., 2., 4., 8.])
_Y = np.array([10., 20., 30.])


def _axis(values, name, unit='', delta=None, time_dependent=False):
    values = np.asarray(values, dtype=float)
    deltas = {} if delta is None else {'delta_plus': np.broadcast_to(delta, values.shape).astype(float),
                                       'delta_minus': np.broadcast_to(delta, values.shape).astype(float)}
    return VariableAxis(values=values, meta={'UNITS': unit}, name=name, is_time_dependent=time_dependent, **deltas)


def _x():
    return _axis(_X, 'x', 'eV', delta=_X / 2)


def _y():
    return _axis(_Y, 'y', 'deg')


def _variable(values=None, axes=None, unit='counts', fill=None):
    axes = axes or [_x(), _y()]
    shape = (_T,) + tuple(a.values.shape[-1] for a in axes)
    values = np.arange(np.prod(shape), dtype=float).reshape(shape) if values is None else values
    meta = {'UNITS': unit, **{f'DEPEND_{i}': a.name for i, a in enumerate(axes, 1)}}
    if fill is not None:
        meta['FILLVAL'] = fill
    return SpeasyVariable(axes=[VariableTimeAxis(values=_TIME)] + axes,
                          values=DataContainer(np.asarray(values, dtype=float), meta=meta, name='v'))


class Dimension(unittest.TestCase):
    def test_an_axis_is_named_or_given_by_dimension(self):
        v = _variable()
        self.assertEqual([dimension(v, axis) for axis in ('x', 'y', 1, 2, -1)], [1, 2, 1, 2, 2])

    def test_it_feeds_numpy(self):
        v = _variable()
        np.testing.assert_array_equal(np.sum(v, axis=dimension(v, 'x')).values, v.values.sum(axis=1))

    def test_time_is_refused_with_how_to_select_it(self):
        v = _variable()
        for axis in (0, 'time'):
            with self.subTest(axis=axis), self.assertRaisesRegex(ValueError, r"(?s)time.*v\[start:stop\]"):
                dimension(v, axis)

    def test_an_unknown_axis_lists_the_axes(self):
        v = _variable()
        with self.assertRaisesRegex(ValueError, r"(?s)No axis 'z'.*'x' \(1\), 'y' \(2\)"):
            dimension(v, 'z')
        with self.assertRaisesRegex(ValueError, r"(?s)No axis 3.*'x' \(1\), 'y' \(2\)"):
            dimension(v, 3)

    def test_two_axes_with_the_same_name_need_a_dimension(self):
        v = _variable(axes=[_axis(_X, 'x'), _axis(_Y, 'x')])
        with self.assertRaisesRegex(ValueError, r"Several axes are named 'x'.*dimension"):
            dimension(v, 'x')

    def test_a_unique_case_insensitive_part_of_a_name_is_enough(self):
        v = _mms_like()
        self.assertEqual([dimension(v, name) for name in ('phi', 'PHI', 'dis_phi', 'theta')], [1, 1, 1, 2])

    def test_an_exact_name_wins_over_parts(self):
        v = _variable(axes=[_axis(_X, 'energy'), _axis(_Y, 'e')])
        self.assertEqual(dimension(v, 'e'), 2)

    def test_an_ambiguous_part_lists_the_matching_axes(self):
        v = _mms_like()
        with self.assertRaisesRegex(ValueError, r"(?s)'dis' matches several axes.*'mms1_dis_phi_fast' \(1\), "
                                                r"'mms1_dis_theta_fast' \(2\)"):
            dimension(v, 'dis')

    def test_the_time_axis_is_never_matched_by_a_part(self):
        v = _variable(axes=[_axis(_X, 'lifetime'), _y()])
        self.assertEqual(dimension(v, 'tim'), 1)

    def test_an_axis_spanning_several_dimensions_has_a_dimension_but_is_not_reducible(self):
        # a fixed axis may hold one value per data cell (CDAWeb map products such as GOLD)
        grid = _axis(np.tile(_X, (3, 1)).T, 'grid')
        v = _variable(axes=[grid, _y()], values=np.ones((_T, 4, 3)))
        self.assertEqual(dimension(v, 'grid'), 1)
        with self.assertRaisesRegex(ValueError, r"'grid' spans several dimensions.*\(4, 3\)"):
            integrate(v, 'grid')


def _mms_like():
    return _variable(axes=[_axis(_X, 'mms1_dis_phi_fast', 'deg'), _axis(_Y, 'mms1_dis_theta_fast', 'deg')])


class Selection(unittest.TestCase):
    def test_the_result_keeps_the_other_axes_and_renumbers_depend(self):
        r = sel(_variable(), 'x', 4.)
        self.assertEqual([a.name for a in r.axes[1:]], ['y'])
        self.assertEqual(r.meta['DEPEND_1'], 'y')
        self.assertNotIn('DEPEND_2', r.meta)

    def test_a_range_keeps_the_axis_deltas(self):
        r = sel(_variable(), 'x', [2., 4.])
        np.testing.assert_array_equal(r.axes[1].delta_plus, [1., 2.])

    def test_sel_a_range_keeps_values_within_both_bounds_in_either_order(self):
        v = _variable()
        for value in (slice(2., 4.), [4., 2.]):
            np.testing.assert_array_equal(sel(v, 'x', value).axes[1].values, [2., 4.])

    def test_sel_a_range_on_a_descending_axis(self):
        v = _variable(axes=[_axis(_X[::-1], 'x'), _y()])
        np.testing.assert_array_equal(sel(v, 'x', slice(1.5, 5.)).axes[1].values, [4., 2.])

    def test_an_open_bound_is_no_limit_like_xarray(self):
        v = _variable()
        for value, kept in ((slice(2., None), [2., 4., 8.]), (slice(None, 4.), [1., 2., 4.]), (slice(None), _X),
                            ([2., None], [2., 4., 8.]), ([None, 2.], [1., 2.])):
            with self.subTest(value=value):
                np.testing.assert_array_equal(sel(v, 'x', value).axes[1].values, kept)

    def test_a_step_is_refused(self):
        v = _variable()
        with self.assertRaisesRegex(ValueError, r"sel takes no step, got slice\(1.0, 8.0, 2.0\): .*v\[:, ::2\]"):
            sel(v, 'x', slice(1., 8., 2.))

    def test_a_range_given_as_a_list_has_two_bounds(self):
        v = _variable()
        for value in ([4.], [1., 2., 3.], []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, r"a range is \[lo, hi\], got"):
                sel(v, 'x', value)

    def test_an_empty_range_is_an_error(self):
        v = _variable()
        with self.assertRaisesRegex(ValueError, r"No value of 'x' in \[100.0, 200.0\] eV"):
            sel(v, 'x', slice(100., 200.))

    def test_sel_a_value_is_exact_unless_nearest_like_xarray(self):
        v = _variable()
        np.testing.assert_array_equal(sel(v, 'x', 4.).values, v.values[:, 2])
        np.testing.assert_array_equal(sel(v, 'x', 5., method='nearest').values, v.values[:, 2])
        with self.assertRaisesRegex(KeyError, "method='nearest'"):
            sel(v, 'x', 5.)

    def test_sel_method_is_none_or_nearest(self):
        v = _variable()
        with self.assertRaisesRegex(ValueError, "method must be None or 'nearest', got 'pad'"):
            sel(v, 'x', 4., method='pad')

    def test_a_record_varying_axis_is_selected_per_record(self):
        energy = _axis(np.array([[1., 2., 4., 8.], [2., 4., 8., 16.], [1., 2., 4., 8.]]), 'e', time_dependent=True)
        v = _variable(axes=[energy, _y()])
        ranged = sel(v, 'e', slice(2., 4.))
        # columns in range in some record are kept, and masked in the records where they are out of range
        np.testing.assert_array_equal(ranged.axes[1].values, energy.values[:, :3])
        self.assertTrue(np.all(np.isnan(ranged.values[0, 0])))
        self.assertTrue(np.all(np.isnan(ranged.values[1, 2])))
        np.testing.assert_array_equal(ranged.values[0, 1:], v.values[0, 1:3])
        np.testing.assert_array_equal(ranged.values[1, :2], v.values[1, :2])
        nearest = sel(v, 'e', 4., method='nearest')
        np.testing.assert_array_equal(nearest.values[1], v.values[1, 1])
        np.testing.assert_array_equal(nearest.values[0], v.values[0, 2])


class Integrate(unittest.TestCase):
    def test_widths_come_from_the_axis_deltas(self):
        v = _variable(np.ones((_T, 4, 3)))
        np.testing.assert_allclose(integrate(v, 'x').values, np.sum(_X))

    def test_explicit_edges_come_first(self):
        v = _variable(np.ones((_T, 4, 3)))
        np.testing.assert_allclose(integrate(v, 'x', edges=[0., 1., 2., 3., 10.]).values, 10.)

    def test_without_deltas_widths_come_from_midpoints(self):
        v = _variable(np.ones((_T, 4, 3)), axes=[_axis([1., 2., 4., 8.], 'x'), _y()])
        # edges 0.5, 1.5, 3, 6, 10
        np.testing.assert_allclose(integrate(v, 'x').values, 9.5)

    def test_a_record_varying_axis_gets_widths_per_record(self):
        energy = _axis(np.array([[1., 2., 3.], [2., 4., 6.], [1., 2., 3.]]), 'e', time_dependent=True)
        r = integrate(_variable(np.ones((_T, 3, 3)), axes=[energy, _y()]), 'e')
        np.testing.assert_allclose(r.values[:, 0], [3., 6., 3.])

    def test_the_unit_is_multiplied_by_the_axis_unit(self):
        self.assertEqual(u.Unit(integrate(_variable(unit='1/(cm2 s sr eV)'), 'x').unit), u.Unit('1/(cm2 s sr)'))
        self.assertEqual(integrate(_variable(unit=''), 'x').unit, 'eV')
        self.assertEqual(integrate(_variable(unit='phase-space density'), 'y').unit, '(phase-space density) deg')
        unitless = _variable(axes=[_axis(_X, 'n'), _y()])
        self.assertEqual(integrate(unitless, 'n').unit, 'counts')

    def test_unsorted_values_without_deltas_are_an_error_saying_what_to_do(self):
        v = _variable(axes=[_axis([1., 4., 2., 8.], 'x'), _y()])
        with self.assertRaisesRegex(ValueError, r"(?s)widths of 'x'.*not sorted.*edges="):
            integrate(v, 'x')

    def test_unusable_deltas_are_an_error(self):
        v = _variable(axes=[_axis(_X, 'x', delta=[1., np.nan, 1., 1.]), _y()])
        with self.assertRaisesRegex(ValueError, r"(?s)widths of 'x'.*DELTA_PLUS_VAR.*edges="):
            integrate(v, 'x')

    def test_nan_and_fill_values_are_ignored_but_all_missing_stays_nan(self):
        values = np.ones((_T, 4, 3))
        values[0, 1, :] = np.nan
        values[1, :, 0] = -1e31
        r = integrate(_variable(values, fill=-1e31), 'x')
        np.testing.assert_array_equal(r.values[0], [13., 13., 13.])
        self.assertTrue(np.isnan(r.values[1, 0]))
        np.testing.assert_array_equal(r.values[2], [15., 15., 15.])

    def test_edges_take_arrays_lists_and_variables(self):
        v = _variable(np.ones((_T, 4, 3)))
        edges = np.array([0., 1., 2., 3., 10.])
        edges_variable = SpeasyVariable(axes=[VariableTimeAxis(values=_TIME[:1])],
                                        values=DataContainer(edges.reshape(1, -1), name='edges'))
        for given in (edges, edges.tolist(), edges_variable):
            with self.subTest(edges=type(given).__name__):
                np.testing.assert_allclose(integrate(v, 'x', edges=given).values, 10.)

    def test_edges_need_one_more_value_than_the_axis(self):
        v = _variable()
        with self.assertRaisesRegex(ValueError, r"edges for 'x' must hold 5 values, got 3"):
            integrate(v, 'x', edges=[1., 2., 3.])


class NoMethods(unittest.TestCase):

    def test_reductions_are_functions_not_variable_methods(self):
        for name in ('isel', 'sel', 'sum', 'mean', 'integrate', 'reduce'):
            with self.subTest(name=name):
                self.assertFalse(hasattr(SpeasyVariable, name))


if __name__ == '__main__':
    unittest.main()
