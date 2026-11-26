"""numpy reductions on a SpeasyVariable with more than one axis besides time: negative and several axes, keepdims,
and which column names survive."""
import unittest

import numpy as np

from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products import SpeasyVariable

_T, _E, _P, _H = 5, 4, 6, 3


def _distribution():
    """(time, energy, phi, theta), with ISTP-like deltas on every axis."""
    time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')

    def axis(values, name):
        return VariableAxis(values=values, name=name, meta={'UNITS': 'eV' if name == 'energy' else 'deg'},
                            delta_plus=values / 2, delta_minus=values / 4)

    return SpeasyVariable(axes=[VariableTimeAxis(values=time), axis(np.array([10., 100., 1e3, 1e4]), 'energy'),
                                axis(np.arange(_P) * 60. + 30., 'phi'), axis(np.array([30., 90., 150.]), 'theta')],
                          values=DataContainer(values=np.arange(_T * _E * _P * _H, dtype=float).reshape(_T, _E, _P, _H),
                                               name='dist', meta={'UNITS': 's^3/cm^6'}),
                          columns=[f"e{i}" for i in range(_E)])


class NumpyAxes(unittest.TestCase):

    def setUp(self):
        self.v = _distribution()

    def test_a_negative_axis_is_the_same_dimension_counted_from_the_end(self):
        r = np.sum(self.v, axis=-1)
        self.assertEqual(r.axes_labels, ['time', 'energy', 'phi'])
        np.testing.assert_array_equal(r.values, np.sum(self.v, axis=3).values)

    def test_several_axes_drop_every_reduced_axis(self):
        for axis in ((2, 3), (-1, 2), (3, -2)):
            with self.subTest(axis=axis):
                r = np.nansum(self.v, axis=axis)
                self.assertEqual(r.axes_labels, ['time', 'energy'])
                np.testing.assert_array_equal(r.values, self.v.values.sum(axis=(2, 3)))
                np.testing.assert_array_equal(r.axes[1].delta_plus, self.v.axes[1].delta_plus)

    def test_reducing_time_among_several_axes_gives_a_plain_array(self):
        r = np.sum(self.v, axis=(0, 2))
        self.assertIsInstance(r, np.ndarray)
        self.assertEqual(r.shape, (_E, _H))

    def test_keepdims_is_refused_with_a_way_out(self):
        v = self.v
        for axis in (2, 0, (0, 2), None):
            with self.subTest(axis=axis), \
                    self.assertRaisesRegex(ValueError, r"keepdims=True is not supported.*np\.sum\(var\.values"):
                np.sum(v, axis=axis, keepdims=True)

    def test_column_names_survive_when_dimension_1_does(self):
        self.assertEqual(np.mean(self.v, axis=2).columns, self.v.columns)
        self.assertEqual(np.mean(self.v, axis=(2, 3)).columns, self.v.columns)
        self.assertEqual(np.mean(self.v, axis=1).columns, [f"column_{i}" for i in range(_P)])


if __name__ == '__main__':
    unittest.main()
