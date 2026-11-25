"""Bin widths (ISTP DELTA_PLUS_VAR / DELTA_MINUS_VAR of an axis variable) carried by VariableAxis."""
import pickle
import unittest

import numpy as np
import pycdfpp

from speasy.core.codecs import get_codec
from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products import SpeasyVariable
from speasy.products.variable import merge

_N, _E, _PHI = 6, 4, 3
_EPOCH = np.arange('2020-01-01T00:00', '2020-01-01T00:01', np.timedelta64(10, 's'), dtype='datetime64[ns]')
_ENERGY = np.array([10., 20., 40., 80.])
_DP, _DM = np.array([4., 8., 16., 32.]), np.array([3., 6., 12., 24.])


def _time_dependent_axis(n=_N):
    values = np.tile(_ENERGY, (n, 1)) * np.arange(1, n + 1)[:, None]
    return VariableAxis(values=values, name='energy', is_time_dependent=True,
                        delta_plus=values * 0.1, delta_minus=values * 0.2)


def _variable(n=_N, start=0):
    time = VariableTimeAxis(values=_EPOCH[start:start + n])
    phi = VariableAxis(values=np.array([0., 120., 240.]), name='phi', delta_plus=np.full(3, 60.),
                       delta_minus=np.full(3, 60.))
    return SpeasyVariable(axes=[time, _time_dependent_axis(n), phi],
                          values=DataContainer(np.random.random((n, _E, _PHI)), name='flux'))


class AxisDeltas(unittest.TestCase):
    def test_an_axis_without_deltas_has_none(self):
        axis = VariableAxis(values=_ENERGY, name='energy')
        self.assertIsNone(axis.delta_plus)
        self.assertIsNone(axis.delta_minus)

    def test_deltas_must_have_the_shape_of_the_values(self):
        short = np.ones(3)
        with self.assertRaisesRegex(ValueError, r"delta_plus of axis 'energy' has shape \(3,\).*\(4,\)"):
            VariableAxis(values=_ENERGY, name='energy', delta_plus=short, delta_minus=short)

    def test_time_slices_slice_the_deltas_of_time_dependent_axes(self):
        v = _variable()[1:3]
        energy = v.axes[1]
        np.testing.assert_array_equal(energy.delta_plus, energy.values * 0.1)
        np.testing.assert_array_equal(energy.delta_minus, energy.values * 0.2)
        self.assertEqual(energy.delta_plus.shape, (2, _E))
        np.testing.assert_array_equal(v.axes[2].delta_plus, np.full(3, 60.))

    def test_merge_keeps_the_deltas(self):
        merged = merge([_variable(3, 0), _variable(3, 3)])
        energy = merged.axes[1]
        self.assertEqual(energy.delta_plus.shape, (_N, _E))
        np.testing.assert_array_equal(energy.delta_plus[3:], _variable(3, 3).axes[1].delta_plus)

    def test_pickle_round_trip(self):
        v = pickle.loads(pickle.dumps(_variable()))
        np.testing.assert_array_equal(v.axes[1].delta_minus, _variable().axes[1].delta_minus)

    def test_an_axis_pickled_before_deltas_existed_has_none(self):
        # an old pickle restores only the __data slot
        old = VariableAxis.__new__(VariableAxis)
        old._VariableAxis__data = DataContainer(_ENERGY, name='energy', is_time_dependent=False)
        axis = pickle.loads(pickle.dumps(old))
        self.assertIsNone(axis.delta_plus)
        self.assertEqual(len(axis[1:3]), 2)

    def test_dictionary_round_trip(self):
        axis = _time_dependent_axis()
        restored = VariableAxis.from_dictionary(axis.to_dictionary(array_to_list=True))
        np.testing.assert_array_equal(restored.delta_plus, axis.delta_plus)
        self.assertEqual(restored, axis)

    def test_data_index_storage_round_trip(self):
        from speasy.data_index._storable import from_storable, to_storable
        from speasy.products.variable import from_dictionary
        v = _variable()
        self.assertEqual(from_dictionary(from_storable(to_storable(v.to_dictionary()))), v)

    def test_axes_with_different_deltas_differ(self):
        a = VariableAxis(values=_ENERGY, name='e', delta_plus=_DP, delta_minus=_DM)
        self.assertNotEqual(a, VariableAxis(values=_ENERGY, name='e'))
        self.assertEqual(a, VariableAxis(values=_ENERGY, name='e', delta_plus=_DP.copy(), delta_minus=_DM.copy()))

    def test_copy_keeps_the_deltas(self):
        np.testing.assert_array_equal(_variable().copy().axes[2].delta_plus, np.full(3, 60.))

    def test_like_copies_and_astype_keep_the_deltas(self):
        axis = VariableAxis(values=_ENERGY, name='e', delta_plus=_DP, delta_minus=_DM)
        for derived in (axis.zeros_like(), axis.ones_like(), axis.empty_like(), axis.astype(np.float32)):
            np.testing.assert_array_equal(derived.delta_plus, _DP)
            np.testing.assert_array_equal(derived.delta_minus, _DM)
            self.assertIsNot(derived.delta_plus, axis.delta_plus)
        np.testing.assert_array_equal(axis.zeros_like().values, np.zeros(_E))

    def test_select_slices_the_deltas(self):
        selected = _time_dependent_axis().select([0, 2])
        np.testing.assert_array_equal(selected.values, _time_dependent_axis().values[[0, 2]])
        np.testing.assert_array_equal(selected.delta_minus, _time_dependent_axis().delta_minus[[0, 2]])

    def test_select_in_place_slices_the_deltas(self):
        axis = _time_dependent_axis()
        expected = axis.delta_plus[1:3].copy()
        self.assertIs(axis.select(slice(1, 3), inplace=True), axis)
        np.testing.assert_array_equal(axis.delta_plus, expected)
        self.assertEqual(axis.delta_minus.shape, (2, _E))


def _cdf(energy_attributes: dict, extra: dict) -> bytes:
    cdf = pycdfpp.CDF()
    cdf.add_variable("Epoch", values=_EPOCH, data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                     attributes={"VAR_TYPE": "support_data"})
    cdf.add_variable("energy", values=_ENERGY.reshape(1, -1), is_nrv=True,
                     attributes={"VAR_TYPE": "support_data", "UNITS": "eV", **energy_attributes})
    cdf.add_variable("energy_tv", values=np.tile(_ENERGY, (_N, 1)),
                     attributes={"VAR_TYPE": "support_data", "DEPEND_0": "Epoch", "UNITS": "eV",
                                 "DELTA_PLUS_VAR": "energy_dp", "DELTA_MINUS_VAR": "energy_dm"})
    for name, (values, attributes) in extra.items():
        cdf.add_variable(name, values=values, is_nrv=values.shape[0] == 1, attributes=attributes)
    cdf.add_variable("flux", values=np.random.random((_N, _E)),
                     attributes={"VAR_TYPE": "data", "DEPEND_0": "Epoch", "DEPEND_1": "energy",
                                 "DELTA_PLUS_VAR": "flux_err", "DELTA_MINUS_VAR": "flux_err"})
    cdf.add_variable("flux_tv", values=np.random.random((_N, _E)),
                     attributes={"VAR_TYPE": "data", "DEPEND_0": "Epoch", "DEPEND_1": "energy_tv"})
    cdf.add_variable("flux_err", values=np.random.random((_N, _E)),
                     attributes={"VAR_TYPE": "support_data", "DEPEND_0": "Epoch"})
    return bytes(pycdfpp.save(cdf))


_DELTAS = {"energy_dp": (_DP.reshape(1, -1), {"VAR_TYPE": "support_data", "FILLVAL": -1e31}),
           "energy_dm": (_DM.reshape(1, -1), {"VAR_TYPE": "support_data"})}


def _load(variable, energy_attributes, extra=_DELTAS):
    return get_codec('cdf').load_variable(variable, file=_cdf(energy_attributes, extra), disable_cache=True)


class IstpCodecLoadsAxisDeltas(unittest.TestCase):
    def test_delta_plus_and_minus_of_the_axis_variable(self):
        v = _load("flux", {"DELTA_PLUS_VAR": "energy_dp", "DELTA_MINUS_VAR": "energy_dm"})
        np.testing.assert_array_equal(v.axes[1].delta_plus, _DP)
        np.testing.assert_array_equal(v.axes[1].delta_minus, _DM)

    def test_a_single_delta_is_used_for_both_sides(self):
        v = _load("flux", {"DELTA_PLUS_VAR": "energy_dp"})
        np.testing.assert_array_equal(v.axes[1].delta_minus, _DP)

    def test_a_constant_delta_is_broadcast_to_a_time_dependent_axis(self):
        v = _load("flux_tv", {})
        self.assertEqual(v.axes[1].delta_plus.shape, (_N, _E))
        np.testing.assert_array_equal(v.axes[1].delta_plus[3], _DP)

    def test_fill_values_in_deltas_become_nan(self):
        dp = _DP.copy()
        dp[2] = -1e31
        deltas = {**_DELTAS, "energy_dp": (dp.reshape(1, -1), _DELTAS["energy_dp"][1])}
        v = _load("flux", {"DELTA_PLUS_VAR": "energy_dp", "DELTA_MINUS_VAR": "energy_dm"}, deltas)
        self.assertTrue(np.isnan(v.axes[1].delta_plus[2]))

    def test_an_axis_without_delta_attributes_has_none(self):
        self.assertIsNone(_load("flux", {}).axes[1].delta_plus)

    def test_a_missing_delta_variable_is_ignored(self):
        self.assertIsNone(_load("flux", {"DELTA_PLUS_VAR": "nope"}, {}).axes[1].delta_plus)

    def test_a_record_varying_delta_is_kept_per_record(self):
        dp = np.tile(_DP, (_N, 1)) * np.arange(1, _N + 1)[:, None]
        deltas = {"energy_dp": (dp, {"VAR_TYPE": "support_data", "DEPEND_0": "Epoch"}),
                  "energy_dm": _DELTAS["energy_dm"]}
        v = _load("flux_tv", {}, deltas)
        np.testing.assert_array_equal(v.axes[1].delta_plus, dp)

    def test_a_non_numeric_delta_is_ignored(self):
        deltas = {"energy_dp": (np.array([["wide"] * _E]), {"VAR_TYPE": "support_data"})}
        self.assertIsNone(_load("flux", {"DELTA_PLUS_VAR": "energy_dp"}, deltas).axes[1].delta_plus)

    def test_a_delta_of_the_wrong_shape_is_ignored(self):
        deltas = {"energy_dp": (np.ones((1, 3)), {"VAR_TYPE": "support_data"})}
        self.assertIsNone(_load("flux", {"DELTA_PLUS_VAR": "energy_dp"}, deltas).axes[1].delta_plus)


if __name__ == '__main__':
    unittest.main()
