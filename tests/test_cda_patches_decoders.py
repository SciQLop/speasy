import unittest
from datetime import datetime

import numpy as np
import pycdfpp
from ddt import ddt, data, unpack

from speasy.data_providers.cda._patches.decoders import TimeMatrix, EpochPlusOffsets, EpochPlusSamplingRate

T0 = np.datetime64('2020-01-01T00:00:00', 'ns')
FILL_F32 = -9.999999848e30


def _tt2000(times):
    return pycdfpp.to_tt2000(np.asarray(times, dtype='datetime64[ns]'))


def _add_time(cdf, name, times):
    cdf.add_variable(name, values=_tt2000(times), data_type=pycdfpp.DataType.CDF_TIME_TT2000)


def _add_data(cdf, name, values, **attributes):
    cdf.add_variable(name, values=values, attributes={k: [v] for k, v in attributes.items()})


def _ns(n):
    return np.timedelta64(int(n), 'ns')


def _epoch_cdf(epoch, values, **attributes):
    cdf = pycdfpp.CDF()
    _add_time(cdf, 'Epoch', epoch)
    _add_data(cdf, 'wave', values, **attributes)
    return cdf


@ddt
class TimeMatrixTest(unittest.TestCase):
    def test_time_matrix_flattens(self):
        time = T0 + np.arange(8).reshape(2, 4) * np.timedelta64(1, 'ms')
        values = np.arange(8, dtype=np.float32).reshape(2, 4)
        cdf = pycdfpp.CDF()
        _add_time(cdf, 'time', time)
        _add_data(cdf, 'wave', values)
        result = TimeMatrix(time='time').decode(cdf, 'wave')
        self.assertEqual(len(result), 8)
        np.testing.assert_array_equal(result.time, time.reshape(-1))
        np.testing.assert_array_equal(result.values.reshape(-1), values.reshape(-1))

    def test_overlapping_buckets_raise(self):
        time = np.stack([T0 + np.arange(4) * np.timedelta64(1, 'ms'),
                         T0 + np.arange(2, 6) * np.timedelta64(1, 'ms')])
        cdf = pycdfpp.CDF()
        _add_time(cdf, 'time', time)
        _add_data(cdf, 'wave', np.zeros((2, 4), dtype=np.float32))
        with self.assertRaisesRegex(ValueError, "not increasing"):
            TimeMatrix(time='time').decode(cdf, 'wave')

    def test_samples_outside_time_valid_range_are_dropped(self):
        time = T0 + np.arange(8).reshape(2, 4) * np.timedelta64(1, 'ms')
        time[:, 2:] = np.datetime64('1999-12-31T23:59:59', 'ns')
        values = np.arange(8, dtype=np.float32).reshape(2, 4)
        cdf = pycdfpp.CDF()
        cdf.add_variable('time', values=_tt2000(time), data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                         attributes={'VALIDMIN': [pycdfpp.to_tt2000(datetime(2019, 12, 31))]})
        _add_data(cdf, 'wave', values)
        result = TimeMatrix(time='time').decode(cdf, 'wave')
        np.testing.assert_array_equal(result.time, time[:, :2].reshape(-1))
        np.testing.assert_array_equal(result.values.reshape(-1), values[:, :2].reshape(-1))

    def test_samples_above_time_valid_max_are_kept(self):
        time = T0 + np.arange(8).reshape(2, 4) * np.timedelta64(1, 'ms')
        cdf = pycdfpp.CDF()
        cdf.add_variable('time', values=_tt2000(time), data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                         attributes={'VALIDMAX': [pycdfpp.to_tt2000(datetime(2019, 12, 31))]})
        _add_data(cdf, 'wave', np.arange(8, dtype=np.float32).reshape(2, 4))
        self.assertEqual(len(TimeMatrix(time='time').decode(cdf, 'wave')), 8)

    def test_zero_records_returns_none(self):
        cdf = pycdfpp.CDF()
        _add_time(cdf, 'time', np.zeros((0, 4), dtype='datetime64[ns]'))
        _add_data(cdf, 'wave', np.zeros((0, 4), dtype=np.float32))
        self.assertIsNone(TimeMatrix(time='time').decode(cdf, 'wave'))


@ddt
class EpochPlusOffsetsTest(unittest.TestCase):
    def test_epoch_plus_offsets_broadcast(self):
        epoch = T0 + np.arange(3) * np.timedelta64(1, 's')
        offsets = np.array([[0, 10, 20, 30]], dtype=np.int64)
        cdf = _epoch_cdf(epoch, np.arange(12, dtype=np.float32).reshape(3, 4))
        cdf.add_variable('off', values=offsets, is_nrv=True)
        result = EpochPlusOffsets(offsets='off', ns_per_unit=1.).decode(cdf, 'wave')
        self.assertEqual(len(result), 12)
        for i in range(3):
            for k in range(4):
                self.assertEqual(result.time[i * 4 + k], epoch[i] + _ns(offsets[0, k]))

    def test_epoch_plus_offsets_per_record_channel_first(self):
        epoch = T0 + np.arange(2) * np.timedelta64(1, 's')
        offsets = np.arange(8, dtype=np.int64).reshape(2, 4)
        values = np.arange(24, dtype=np.float32).reshape(2, 3, 4)
        cdf = _epoch_cdf(epoch, values)
        cdf.add_variable('off', values=offsets)
        result = EpochPlusOffsets(offsets='off', ns_per_unit=1., sample_axis=2).decode(cdf, 'wave')
        self.assertEqual(result.values.shape, (8, 3))
        np.testing.assert_array_equal(result.values[:4, 1], values[0, 1])
        self.assertEqual(result.time[5], epoch[1] + _ns(5))
        self.assertEqual(list(result.columns), ['component_0', 'component_1', 'component_2'])

    def test_offset_unit(self):
        epoch = T0 + np.arange(1) * np.timedelta64(1, 's')
        cdf = _epoch_cdf(epoch, np.zeros((1, 3), dtype=np.float32))
        cdf.add_variable('off', values=np.array([[0., 1.5, 3.]]), is_nrv=True)
        result = EpochPlusOffsets(offsets='off', ns_per_unit=1e3).decode(cdf, 'wave')
        np.testing.assert_array_equal(result.time - epoch[0], [_ns(0), _ns(1500), _ns(3000)])

    def test_labels_come_from_label_pointer(self):
        epoch = T0 + np.arange(1) * np.timedelta64(1, 's')
        cdf = _epoch_cdf(epoch, np.zeros((1, 2, 3), dtype=np.float32), LABL_PTR_1='labels')
        cdf.add_variable('labels', values=['Bx', 'By'], is_nrv=True)
        cdf.add_variable('off', values=np.array([[0, 1, 2]]), is_nrv=True)
        result = EpochPlusOffsets(offsets='off', ns_per_unit=1., sample_axis=2).decode(cdf, 'wave')
        self.assertEqual(list(result.columns), ['Bx', 'By'])

    @data((np.float32, FILL_F32), (np.int8, -128))
    @unpack
    def test_fill_becomes_nan(self, dtype, fill):
        epoch = T0 + np.arange(1) * np.timedelta64(1, 's')
        values = np.array([[1, fill, 3]], dtype=dtype)
        cdf = _epoch_cdf(epoch, values, FILLVAL=dtype(fill))
        cdf.add_variable('off', values=np.array([[0, 1, 2]]), is_nrv=True)
        result = EpochPlusOffsets(offsets='off', ns_per_unit=1.).decode(cdf, 'wave')
        np.testing.assert_array_equal(np.isnan(result.values.reshape(-1)), [False, True, False])


class EpochPlusSamplingRateTest(unittest.TestCase):
    def test_sampling_rate_selects_records(self):
        epoch = T0 + np.arange(3) * np.timedelta64(1, 's')
        cdf = _epoch_cdf(epoch, np.arange(12, dtype=np.float32).reshape(3, 4))
        cdf.add_variable('rate', values=np.array([256, 4096, 256], dtype=np.int32))
        result = EpochPlusSamplingRate(rate='rate', rate_hz=256).decode(cdf, 'wave')
        self.assertEqual(len(result), 8)
        np.testing.assert_array_equal(result.values.reshape(-1), [0, 1, 2, 3, 8, 9, 10, 11])
        step = np.timedelta64(int(1e9 / 256), 'ns')
        self.assertEqual(result.time[1] - result.time[0], step)
        self.assertEqual(result.time[4], epoch[2])

    def test_no_record_at_rate_returns_none(self):
        epoch = T0 + np.arange(2) * np.timedelta64(1, 's')
        cdf = _epoch_cdf(epoch, np.zeros((2, 4), dtype=np.float32))
        cdf.add_variable('rate', values=np.array([256, 256], dtype=np.int32))
        self.assertIsNone(EpochPlusSamplingRate(rate='rate', rate_hz=4096).decode(cdf, 'wave'))


class EpochPlusSamplingRateAnyRateTest(unittest.TestCase):
    def test_no_rate_keeps_every_record_at_its_own_rate(self):
        epoch = T0 + np.arange(2) * np.timedelta64(1, 's')
        cdf = _epoch_cdf(epoch, np.zeros((2, 4), dtype=np.float32))
        cdf.add_variable('rate', values=np.array([256, 4096], dtype=np.float32))
        result = EpochPlusSamplingRate(rate='rate').decode(cdf, 'wave')
        self.assertEqual(len(result), 8)
        self.assertEqual(result.time[1] - result.time[0], _ns(1e9 / 256))
        self.assertEqual(result.time[5] - result.time[4], _ns(round(1e9 / 4096)))
        self.assertEqual(result.time[4], epoch[1])
