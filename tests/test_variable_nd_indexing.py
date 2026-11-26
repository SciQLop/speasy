"""Indexing a SpeasyVariable along any dimension: v[:, :, 3] drops the axis, v[:, :, 1:3] keeps part of it."""
import unittest

import numpy as np

from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products import SpeasyVariable

_T, _E, _P, _H = 5, 4, 6, 3
_ENERGIES = np.array([10., 100., 1e3, 1e4])


def _axis(values, name, time_dependent=False):
    return VariableAxis(values=values, name=name, is_time_dependent=time_dependent,
                        delta_plus=values / 2, delta_minus=values / 4)


def _distribution(record_varying_energy=False):
    """(time, energy, phi, theta); the energy axis may vary with time, as MMS FPI's does."""
    time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')
    energy = (_axis(_ENERGIES * (1 + np.arange(_T))[:, None], 'energy', time_dependent=True)
              if record_varying_energy else _axis(_ENERGIES, 'energy'))
    return SpeasyVariable(axes=[VariableTimeAxis(values=time), energy, _axis(np.arange(_P) * 60. + 30., 'phi'),
                                _axis(np.array([30., 90., 150.]), 'theta')],
                          values=DataContainer(values=np.arange(_T * _E * _P * _H, dtype=float).reshape(_T, _E, _P, _H),
                                               name='dist', meta={'UNITS': 's^3/cm^6', 'FILLVAL': -1e31}),
                          columns=[f"e{i}" for i in range(_E)])


class Indexing(unittest.TestCase):

    def setUp(self):
        self.v = _distribution()

    def test_an_integer_drops_the_axis(self):
        r = self.v[:, :, 3]
        self.assertEqual(r.axes_labels, ['time', 'energy', 'theta'])
        np.testing.assert_array_equal(r.values, self.v.values[:, :, 3])
        self.assertEqual(r.meta, self.v.meta)
        self.assertEqual(r.columns, self.v.columns)

    def test_a_slice_keeps_the_axis_with_its_deltas(self):
        r = self.v[:, :, 1:3]
        self.assertEqual(r.axes_labels, ['time', 'energy', 'phi', 'theta'])
        np.testing.assert_array_equal(r.values, self.v.values[:, :, 1:3])
        np.testing.assert_array_equal(r.axes[2].values, [90., 150.])
        np.testing.assert_array_equal(r.axes[2].delta_plus, [45., 75.])
        np.testing.assert_array_equal(r.axes[2].delta_minus, [22.5, 37.5])

    def test_several_dimensions_at_once(self):
        r = self.v[:, 1:3, 0, -1]
        self.assertEqual(r.axes_labels, ['time', 'energy'])
        np.testing.assert_array_equal(r.values, self.v.values[:, 1:3, 0, -1])
        np.testing.assert_array_equal(r.axes[1].values, [100., 1e3])
        self.assertEqual(r.columns, ['e1', 'e2'])

    def test_rows_are_selected_as_before(self):
        r = self.v[1:3, :, 3]
        np.testing.assert_array_equal(r.values, self.v.values[1:3, :, 3])
        np.testing.assert_array_equal(r.time, self.v.time[1:3])

    def test_dimension_1_of_a_distribution(self):
        r = self.v[:, 2]
        self.assertEqual(r.axes_labels, ['time', 'phi', 'theta'])
        np.testing.assert_array_equal(r.values, self.v.values[:, 2])

    def test_a_record_varying_axis_keeps_its_time_dimension(self):
        v = _distribution(record_varying_energy=True)
        r = v[:, 1:3, 0]
        self.assertTrue(r.axes[1].is_time_dependent)
        np.testing.assert_array_equal(r.axes[1].values, v.axes[1].values[:, 1:3])
        np.testing.assert_array_equal(r.axes[1].delta_plus, v.axes[1].delta_plus[:, 1:3])
        self.assertEqual(r.axes_labels, ['time', 'energy', 'theta'])
        self.assertEqual(v[:, 2].axes_labels, ['time', 'phi', 'theta'])

    def test_rows_by_mask(self):
        mask = np.array([True, False, True, False, True])
        r = self.v[mask, :, 3]
        np.testing.assert_array_equal(r.values, self.v.values[mask][:, :, 3])

    def test_grid_axes_spanning_every_dimension_are_cut_too(self):
        time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')
        latitude, longitude = np.meshgrid(np.arange(3.), np.arange(4.), indexing='ij')
        v = SpeasyVariable(axes=[VariableTimeAxis(values=time), VariableAxis(values=latitude, name='lat'),
                                 VariableAxis(values=longitude, name='lon')],
                           values=DataContainer(values=np.ones((_T, 3, 4)), name='map'))
        r = v[:, 1]
        self.assertEqual(r.axes_labels, ['time', 'lon'])
        np.testing.assert_array_equal(r.axes[1].values, longitude[1])
        r = v[:, 0:2, 3]
        self.assertEqual(r.axes_labels, ['time', 'lat'])
        np.testing.assert_array_equal(r.axes[1].values, latitude[0:2, 3])

    def test_two_keys_on_a_table_still_pick_columns(self):
        time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')
        table = SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                               values=DataContainer(values=np.ones((_T, 3)), name='b'), columns=['x', 'y', 'z'])
        self.assertEqual(table[:, 'y'].columns, ['y'])
        self.assertEqual(table[:, 1].columns, ['y'])

    def test_a_grid_axis_varying_with_time_is_cut_on_the_same_dimension(self):
        time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')
        latitude = np.broadcast_to(np.arange(3.)[:, None], (_T, 3, 4)) + np.arange(_T)[:, None, None]
        longitude = np.broadcast_to(np.arange(4.), (_T, 3, 4))
        v = SpeasyVariable(axes=[VariableTimeAxis(values=time),
                                 VariableAxis(values=latitude, name='lat', is_time_dependent=True),
                                 VariableAxis(values=longitude, name='lon', is_time_dependent=True)],
                           values=DataContainer(values=np.ones((_T, 3, 4)), name='map'))
        r = v[:, 1]
        self.assertEqual(r.axes_labels, ['time', 'lon'])
        np.testing.assert_array_equal(r.axes[1].values, longitude[:, 1])

    def test_columns_of_a_record_varying_spectrogram_cut_its_axis_per_record(self):
        time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')
        energy = _axis(_ENERGIES * (1 + np.arange(_T))[:, None], 'energy', time_dependent=True)
        spectrogram = SpeasyVariable(axes=[VariableTimeAxis(values=time), energy],
                                     values=DataContainer(values=np.ones((_T, _E)), name='flux'),
                                     columns=[f"e{i}" for i in range(_E)])
        r = spectrogram[:, 1:3]
        np.testing.assert_array_equal(r.axes[1].values, energy.values[:, 1:3])
        np.testing.assert_array_equal(r.axes[1].delta_plus, energy.delta_plus[:, 1:3])
        self.assertEqual(r.columns, ['e1', 'e2'])

    def test_too_many_indices_is_an_error(self):
        v = self.v
        with self.assertRaisesRegex(IndexError, r"5 indices for a variable with 4 dimensions"):
            _ = v[:, 0, 0, 0, 0]

    def test_other_keys_say_what_is_supported(self):
        v = self.v
        with self.assertRaisesRegex(ValueError, r"dimension 2 takes an int or a slice, got \[1, 2\]"):
            _ = v[:, :, [1, 2]]


class ColumnNamesStillPickColumns(unittest.TestCase):
    """Only ints, slices and row masks index dimensions: names keep picking columns, as before."""

    def setUp(self):
        time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')
        self.table = SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                                    values=DataContainer(values=np.arange(_T * 3.).reshape(_T, 3), name='b'),
                                    columns=['x', 'y', 'z'])

    def test_a_tuple_of_two_names(self):
        r = self.table['x', 'z']
        self.assertEqual(r.columns, ['x', 'z'])
        np.testing.assert_array_equal(r.values, self.table.values[:, [0, 2]])

    def test_a_tuple_of_three_names(self):
        r = self.table['z', 'x', 'y']
        self.assertEqual(r.columns, ['z', 'x', 'y'])
        np.testing.assert_array_equal(r.values, self.table.values[:, [2, 0, 1]])

    def test_names_on_a_distribution_get_the_same_answer_as_before(self):
        v = _distribution()
        for key in (('e1', 'e3'), ('e0', 'e1', 'e2'), (slice(1, 3), ['e1', 'e2'])):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "only supported for table-like variables"):
                _ = v[key]


class ColumnsByPosition(unittest.TestCase):
    """A variable without column names, as sel and integrate return, is indexed by position like any other."""

    def setUp(self):
        time = np.arange('2020-01-01', '2020-01-01T00:00:05', np.timedelta64(1, 's'), dtype='datetime64[ns]')
        self.unnamed = SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                                      values=DataContainer(values=np.arange(_T * 3.).reshape(_T, 3), name='u'))

    def test_an_int_picks_that_column(self):
        r = self.unnamed[:, 1]
        np.testing.assert_array_equal(r.values, self.unnamed.values[:, 1:2])
        self.assertEqual(r.columns, ['column_1'])

    def test_a_slice_and_rows(self):
        r = self.unnamed[1:3, 0:2]
        np.testing.assert_array_equal(r.values, self.unnamed.values[1:3, 0:2])

    def test_out_of_range_says_how_many_columns_there_are(self):
        with self.assertRaisesRegex(IndexError, "3 columns"):
            _ = self.unnamed[:, 5]


if __name__ == '__main__':
    unittest.main()
