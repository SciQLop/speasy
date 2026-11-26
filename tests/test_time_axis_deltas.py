"""The time axis carries the Epoch's DELTA_PLUS_VAR / DELTA_MINUS_VAR (ISTP 4.2.1, 5.2.7) as durations, like the
other axes carry theirs."""
import os
import pickle
import unittest

import numpy as np
import pycdfpp

from speasy.core.codecs import get_codec
from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products import SpeasyVariable
from speasy.products.variable import merge

_N = 6
_EPOCH = np.arange('2020-01-01T00:00', '2020-01-01T00:01', np.timedelta64(10, 's'), dtype='datetime64[ns]')
_DP = (np.arange(1, _N + 1) * np.timedelta64(1, 's')).astype('timedelta64[ns]')
_DM = np.zeros(_N, dtype='timedelta64[ns]')


def _time(n=_N, start=0, deltas=True):
    rows = slice(start, start + n)
    return VariableTimeAxis(values=_EPOCH[rows], **({'delta_plus': _DP[rows], 'delta_minus': _DM[rows]} if deltas else {}))


def _variable(n=_N, start=0, deltas=True):
    return SpeasyVariable(axes=[_time(n, start, deltas)], values=DataContainer(np.arange(n * 3.).reshape(n, 3), name='b'),
                          columns=['x', 'y', 'z'])


class TimeAxisDeltas(unittest.TestCase):
    def test_none_by_default(self):
        self.assertIsNone(VariableTimeAxis(values=_EPOCH).delta_plus)
        self.assertIsNone(VariableTimeAxis(values=_EPOCH).delta_minus)

    def test_durations_one_per_record(self):
        self.assertEqual(_time().delta_plus.dtype, np.dtype('timedelta64[ns]'))
        np.testing.assert_array_equal(_time().delta_plus, _DP)

    def test_shape_and_type_are_checked(self):
        with self.assertRaisesRegex(ValueError, r"delta_plus of axis 'time' has shape \(3,\).*\(6,\)"):
            VariableTimeAxis(values=_EPOCH, delta_plus=_DP[:3])
        with self.assertRaisesRegex(ValueError, r"delta_plus of axis 'time' must be durations \(timedelta64\), got float64"):
            VariableTimeAxis(values=_EPOCH, delta_plus=np.ones(_N))

    def test_row_time_and_mask_selections_select_the_deltas(self):
        mask = np.array([True, False, True, False, True, False])
        by_time = _variable()['2020-01-01T00:00:10':'2020-01-01T00:00:30']
        for selected, rows in ((_variable()[1:3], slice(1, 3)), (by_time, slice(1, 3)), (_variable()[mask], mask)):
            with self.subTest(rows=rows):
                np.testing.assert_array_equal(selected.axes[0].delta_plus, _DP[rows])
                np.testing.assert_array_equal(selected.axes[0].delta_minus, _DM[rows])
        np.testing.assert_array_equal(_time().select([0, 2]).delta_plus, _DP[[0, 2]])

    def test_select_in_place_selects_the_deltas(self):
        time = _time()
        self.assertIs(time.select(slice(1, 3), inplace=True), time)
        np.testing.assert_array_equal(time.values, _EPOCH[1:3])
        np.testing.assert_array_equal(time.delta_plus, _DP[1:3])
        np.testing.assert_array_equal(time.delta_minus, _DM[1:3])

    def test_merge_keeps_the_deltas(self):
        np.testing.assert_array_equal(merge([_variable(3, 0), _variable(3, 3)]).axes[0].delta_plus, _DP)

    def test_copies_like_and_astype_keep_the_deltas(self):
        time = _time()
        for derived in (_variable().copy().axes[0], time.zeros_like(), time.ones_like(), time.empty_like(),
                        time.astype('datetime64[ns]')):
            np.testing.assert_array_equal(derived.delta_plus, _DP)
            self.assertIsNot(derived.delta_plus, time.delta_plus)

    def test_pickle_round_trip(self):
        v = _variable()
        self.assertEqual(pickle.loads(pickle.dumps(v)), v)

    def test_a_time_axis_pickled_before_deltas_existed_has_none(self):
        old = VariableTimeAxis.__new__(VariableTimeAxis)
        old._VariableTimeAxis__data = DataContainer(_EPOCH, name='time')
        time = pickle.loads(pickle.dumps(old))
        self.assertIsNone(time.delta_plus)
        self.assertEqual(len(time[1:3]), 2)

    def test_dictionary_and_data_index_round_trips(self):
        from speasy.data_index._storable import from_storable, to_storable
        from speasy.products.variable import from_dictionary
        for array_to_list in (False, True):
            with self.subTest(array_to_list=array_to_list):
                self.assertEqual(VariableTimeAxis.from_dictionary(_time().to_dictionary(array_to_list)), _time())
        v = _variable()
        self.assertEqual(from_dictionary(from_storable(to_storable(v.to_dictionary()))), v)

    def test_different_deltas_differ(self):
        self.assertNotEqual(_time(), _time(deltas=False))

    def test_reductions_and_column_selections_keep_them(self):
        dist = SpeasyVariable(axes=[_time(), VariableAxis(values=np.array([1., 2.]), name='e'),
                                    VariableAxis(values=np.array([10., 20., 30.]), name='phi')],
                              values=DataContainer(np.ones((_N, 2, 3)), name='dist'))
        for result in (np.nansum(dist, axis=2), dist[:, 1], dist[:, :, 0:2], _variable()[['x', 'y']]):
            np.testing.assert_array_equal(result.axes[0].delta_plus, _DP)


def _cdf(epoch_attributes: dict, deltas: dict, epoch_type=pycdfpp.DataType.CDF_TIME_TT2000) -> bytes:
    cdf = pycdfpp.CDF()
    cdf.add_variable("Epoch", values=_EPOCH, data_type=epoch_type, attributes={"VAR_TYPE": "support_data",
                                                                               **epoch_attributes})
    for name, (values, attributes, nrv) in deltas.items():
        cdf.add_variable(name, values=values, is_nrv=nrv, attributes={"VAR_TYPE": "support_data", **attributes})
    cdf.add_variable("flux", values=np.ones(_N), attributes={"VAR_TYPE": "data", "DEPEND_0": "Epoch"})
    return bytes(pycdfpp.save(cdf))


def _time_of(epoch_attributes, deltas=None, **kwargs) -> VariableTimeAxis:
    return get_codec('cdf').load_variable('flux', file=_cdf(epoch_attributes, deltas or {}, **kwargs),
                                          disable_cache=True).axes[0]


_PAIR = {"DELTA_PLUS_VAR": "Epoch_plus_var", "DELTA_MINUS_VAR": "Epoch_minus_var"}
_FPI_LIKE = {"Epoch_plus_var": (np.array([4.5], dtype=np.float32), {"UNITS": "s"}, True),
             "Epoch_minus_var": (np.array([0.], dtype=np.float32), {"UNITS": "s"}, True)}


class IstpCodecLoadsTimeDeltas(unittest.TestCase):
    def test_a_constant_in_its_own_units_is_spread_over_the_records(self):
        time = _time_of(_PAIR, _FPI_LIKE)
        np.testing.assert_array_equal(time.delta_plus, np.full(_N, np.timedelta64(4500, 'ms')))
        np.testing.assert_array_equal(time.delta_minus, np.zeros(_N, dtype='timedelta64[ns]'))

    def test_a_record_varying_delta_is_kept_per_record(self):
        deltas = {"Epoch_plus_var": (np.arange(1., _N + 1), {"UNITS": "s", "DEPEND_0": "Epoch"}, False),
                  "Epoch_minus_var": _FPI_LIKE["Epoch_minus_var"]}
        np.testing.assert_array_equal(_time_of(_PAIR, deltas).delta_plus, _DP)

    def test_a_lone_delta_leaves_the_other_side_none(self):
        time = _time_of({"DELTA_PLUS_VAR": "Epoch_plus_var"}, _FPI_LIKE)
        self.assertEqual(time.delta_plus[0], np.timedelta64(4500, 'ms'))
        self.assertIsNone(time.delta_minus)

    def test_without_units_a_delta_is_in_the_epoch_unit(self):
        # ISTP 5.2.7: same type as the time variable; 5.2.37: ns for TT2000, ms for CDF_EPOCH
        deltas = {"Epoch_plus_var": (np.array([1500], dtype=np.int64), {}, True)}
        self.assertEqual(_time_of({"DELTA_PLUS_VAR": "Epoch_plus_var"}, deltas).delta_plus[0], np.timedelta64(1500, 'ns'))
        epoch_ms = _time_of({"DELTA_PLUS_VAR": "Epoch_plus_var"}, {"Epoch_plus_var": (np.array([1500.]), {}, True)},
                            epoch_type=pycdfpp.DataType.CDF_EPOCH)
        self.assertEqual(epoch_ms.delta_plus[0], np.timedelta64(1500, 'ms'))

    def test_the_value_attribute_form_like_cluster_cis(self):
        # Cluster CIS 3D: time tags at the acquisition start, DELTA_PLUS_VAR = duration, DELTA_MINUS = 0.0
        deltas = {"duration": (np.arange(1., _N + 1), {"UNITS": "s", "DEPEND_0": "Epoch"}, False)}
        time = _time_of({"DELTA_PLUS_VAR": "duration", "DELTA_MINUS": 0.0}, deltas, epoch_type=pycdfpp.DataType.CDF_EPOCH)
        np.testing.assert_array_equal(time.delta_plus, _DP)
        np.testing.assert_array_equal(time.delta_minus, np.zeros(_N, dtype='timedelta64[ns]'))

    def test_fill_values_become_nat(self):
        attributes = {"UNITS": "s", "FILLVAL": -1e31, "DEPEND_0": "Epoch"}
        deltas = {"Epoch_plus_var": (np.array([1., -1e31, 1., 1., 1., 1.]), attributes, False)}
        time = _time_of({"DELTA_PLUS_VAR": "Epoch_plus_var"}, deltas)
        self.assertTrue(np.isnat(time.delta_plus[1]))

    def test_a_delta_whose_units_are_not_a_duration_is_not_read(self):
        deltas = {"Epoch_plus_var": (np.array([4.5]), {"UNITS": "eV"}, True)}
        self.assertIsNone(_time_of({"DELTA_PLUS_VAR": "Epoch_plus_var"}, deltas).delta_plus)

    def test_an_epoch_without_deltas_has_none(self):
        self.assertIsNone(_time_of({}).delta_plus)


@unittest.skipUnless('SPEASY_LONG_TESTS' in os.environ, "downloads MMS FPI and Cluster CIS distributions")
class TimeDeltasOfRealProducts(unittest.TestCase):
    """What each data file declares (needs a pyistp taking UNITS from the file holding the values)."""

    def _time(self, product, start, stop):
        import speasy as spz
        return spz.get_data(product, start, stop).axes[0]

    def test_mms_fpi_fast_and_burst(self):
        for product, start, stop, plus in (
                ('cda/MMS1_FPI_FAST_L2_DIS-DIST/mms1_dis_dist_fast', '2015-10-16T13:00', '2015-10-16T13:01', 4500),
                ('cda/MMS1_FPI_BRST_L2_DIS-DIST/mms1_dis_dist_brst', '2015-10-16T13:06', '2015-10-16T13:06:10', 150)):
            with self.subTest(product=product):
                time = self._time(product, start, stop)
                # the files store these as float32 seconds: 0.15 s is 0.150000006 s
                np.testing.assert_allclose(time.delta_plus.astype(np.int64), np.full(len(time), plus * 1e6), rtol=1e-7)
                np.testing.assert_array_equal(time.delta_minus, np.zeros(len(time), dtype='timedelta64[ns]'))

    def test_cluster_cis_3d_is_the_duration_after_the_start(self):
        time = self._time('cda/C1_CP_CIS-HIA_HS_MAG_IONS_PEF/ions_3d__C1_CP_CIS_HIA_HS_MAG_IONS_PEF',
                          '2003-02-02T10:00', '2003-02-02T10:10')
        self.assertTrue(np.all(time.delta_plus > np.timedelta64(10, 's')))
        np.testing.assert_array_equal(time.delta_minus, np.zeros(len(time), dtype='timedelta64[ns]'))


if __name__ == '__main__':
    unittest.main()
