import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import numpy as np
import pycdfpp

from speasy.core.direct_archive_downloader import get_product
from speasy.core.inventory.indexes import DatasetIndex, ParameterIndex
from speasy.data_providers.cda import CdaWebException, _archive_params_for
from speasy.data_providers.cda._patches import reader, table
from speasy.data_providers.cda._patches.decoders import TimeMatrix
from speasy.data_providers.cda._patches.reader import patched_reader
from speasy.data_providers.cda._patches.table import InjectedDataset, PatchedParameter

DATASET = 'TEST_PATCHED_DS'
ENTRY = PatchedParameter(DATASET, 'wave', 'wave', TimeMatrix(time='time'))
MS = np.timedelta64(1, 'ms')


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _write_day(folder, day: np.datetime64, n_records=3, bucket=4, time=None):
    time = day + np.arange(n_records * bucket).reshape(n_records, bucket) * MS if time is None else time
    cdf = pycdfpp.CDF()
    cdf.add_variable('time', values=pycdfpp.to_tt2000(time.astype('datetime64[ns]')),
                     data_type=pycdfpp.DataType.CDF_TIME_TT2000)
    cdf.add_variable('wave', values=np.arange(time.size, dtype=np.float32).reshape(time.shape))
    pycdfpp.save(cdf, f"{folder}/test_{str(day)[:10].replace('-', '')}_v01.cdf")
    return time.reshape(-1)


def _dataset(folder):
    return DatasetIndex(name=DATASET, provider='cda', uid=DATASET,
                        meta={'filenaming': 'test_%Y%m%d_v01.cdf',
                              'subdividedby': 'None', 'url': f'file://{folder}',
                              'mastercdf': f'file://{folder}/master.cdf'})


def _parameter(name='wave', **meta):
    return ParameterIndex(name=name, provider='cda', uid=f'{DATASET}/{name}', meta=meta)


def _read(folder, start, stop, parameter=None):
    params = _archive_params_for(_dataset(folder), parameter or _parameter(), 'wave', start, stop)
    return get_product(variable='wave', start_time=start, stop_time=stop, **params)


class PatchedReadPath(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = self._tmp.name
        patcher = mock.patch.object(table, 'PATCHES', (ENTRY,))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_patched_product_reads_flat(self):
        time = _write_day(self.folder, np.datetime64('2020-01-01'))
        v = _read(self.folder, _utc(2020, 1, 1), _utc(2020, 1, 2))
        self.assertEqual(v.values.shape, (12, 1))
        np.testing.assert_array_equal(v.time, time)
        np.testing.assert_array_equal(v.values.reshape(-1), np.arange(12))

    def test_window_inside_bucket(self):
        _write_day(self.folder, np.datetime64('2020-01-01'))
        v = _read(self.folder, _utc(2020, 1, 1, 0, 0, 0, 2000), _utc(2020, 1, 1, 0, 0, 0, 4000))
        self.assertEqual(len(v), 2)
        np.testing.assert_array_equal(v.values.reshape(-1), [2, 3])

    def test_two_files_merge(self):
        first = _write_day(self.folder, np.datetime64('2020-01-01'))
        second = _write_day(self.folder, np.datetime64('2020-01-02'))
        v = _read(self.folder, _utc(2020, 1, 1), _utc(2020, 1, 3))
        self.assertEqual(len(v), len(first) + len(second))
        self.assertTrue(np.all(np.diff(v.time) > np.timedelta64(0, 'ns')))

    def test_unpatched_params_unchanged(self):
        _write_day(self.folder, np.datetime64('2020-01-01'))
        params = _archive_params_for(_dataset(self.folder), _parameter('other'), 'other',
                                     _utc(2020, 1, 1), _utc(2020, 1, 2))
        self.assertEqual(params, {
            'url_pattern': f'file://{self.folder}/test_[12]\\d\\d\\d[01]\\d[0-3]\\d_v01.cdf',
            'split_rule': 'random',
            'split_frequency': 'none',
            'fname_regex': 'test_(?P<start>\\d+t?T?\\d+)_v01.cdf',
            'use_file_list': True,
            'date_format': '%Y%m%d',
            'master_cdf_url': f'file://{self.folder}/master.cdf',
        })

    def test_virtual_patched_param_goes_to_archive(self):
        _write_day(self.folder, np.datetime64('2020-01-01'))
        params = _archive_params_for(_dataset(self.folder), _parameter(VIRTUAL='TRUE'), 'wave',
                                     _utc(2020, 1, 1), _utc(2020, 1, 2))
        self.assertIsNotNone(params)
        self.assertNotIn('master_cdf_url', params)

    def test_probe_failure_falls_back_to_web_service(self):
        with open(f'{self.folder}/test_20200101_v01.cdf', 'wb') as f:
            f.write(b'not a cdf')
        self.assertIsNone(_archive_params_for(_dataset(self.folder), _parameter(), 'wave',
                                              _utc(2020, 1, 1), _utc(2020, 1, 2)))

    def test_injected_probe_failure_raises(self):
        with open(f'{self.folder}/test_20200101_v01.cdf', 'wb') as f:
            f.write(b'not a cdf')
        injected = InjectedDataset(DATASET, 'OTHER', 'test_%Y%m%d_v01.cdf', f'file://{self.folder}', 'None',
                                   'master.cdf', '2020-01-01', 'd')
        with mock.patch.object(table, 'INJECTED', (injected,)):
            with self.assertRaisesRegex(CdaWebException, "only served from files.*test_20200101_v01.cdf"):
                _archive_params_for(_dataset(self.folder), _parameter(), 'wave', _utc(2020, 1, 1), _utc(2020, 1, 2))

    def test_injected_without_file_keeps_archive(self):
        injected = InjectedDataset(DATASET, 'OTHER', 'test_%Y%m%d_v01.cdf', f'file://{self.folder}', 'None',
                                   'master.cdf', '2020-01-01', 'd')
        with mock.patch.object(table, 'INJECTED', (injected,)):
            self.assertIsNone(_read(self.folder, _utc(2020, 1, 1), _utc(2020, 1, 2)))

    def test_unordered_file_error_names_dataset_and_file(self):
        day = np.datetime64('2020-01-01')
        _write_day(self.folder, day, time=day + np.array([[2, 3], [0, 1]]) * MS)
        url = f'file://{self.folder}/test_20200101_v01.cdf'
        with self.assertRaisesRegex(ValueError, f"{DATASET}.*{url}"):
            patched_reader(ENTRY)(url, 'wave')

    def test_empty_first_file_still_reads_flat(self):
        day = np.datetime64('2020-01-01')
        _write_day(self.folder, day, n_records=0)
        second = _write_day(self.folder, day + np.timedelta64(1, 'D'))
        v = _read(self.folder, _utc(2020, 1, 1), _utc(2020, 1, 3))
        np.testing.assert_array_equal(v.time, second)

    def test_decode_error_on_patched_dataset_suggests_api(self):
        day = np.datetime64('2020-01-01')
        _write_day(self.folder, day, time=day + np.array([[2, 3], [0, 1]]) * MS)
        url = f'file://{self.folder}/test_20200101_v01.cdf'
        with self.assertRaisesRegex(ValueError, "method='API'") as ctx:
            patched_reader(ENTRY)(url, 'wave')
        self.assertNotIn('Retry', str(ctx.exception))

    def test_decode_error_on_injected_dataset_asks_for_a_report(self):
        day = np.datetime64('2020-01-01')
        _write_day(self.folder, day, time=day + np.array([[2, 3], [0, 1]]) * MS)
        url = f'file://{self.folder}/test_20200101_v01.cdf'
        injected = InjectedDataset(DATASET, 'OTHER', 'test_%Y%m%d_v01.cdf', f'file://{self.folder}', 'None',
                                   'master.cdf', '2020-01-01', 'd')
        with mock.patch.object(table, 'INJECTED', (injected,)):
            with self.assertRaisesRegex(ValueError, "report it to the speasy developers") as ctx:
                patched_reader(ENTRY)(url, 'wave')
        self.assertNotIn("method='API'", str(ctx.exception))

    def test_transient_error_says_retry(self):
        with mock.patch.object(reader, '_load', side_effect=OSError('connection reset')):
            with self.assertRaisesRegex(OSError, "connection reset.*Retry later"):
                patched_reader(ENTRY)('file:///nowhere.cdf', 'wave')

    def test_decoder_is_part_of_the_cache_key(self):
        day = np.datetime64('2020-01-01')
        time = _write_day(self.folder, day)
        path = f'{self.folder}/test_20200101_v01.cdf'
        url = f'file://{path}'
        first = reader._read_patched(url, DATASET, 'wave', TimeMatrix(time='time'))
        cdf = pycdfpp.load(path)
        cdf.add_variable('other_time', values=pycdfpp.to_tt2000((time + MS).reshape(3, 4).astype('datetime64[ns]')),
                         data_type=pycdfpp.DataType.CDF_TIME_TT2000)
        pycdfpp.save(cdf, path)
        second = reader._read_patched(url, DATASET, 'wave', TimeMatrix(time='other_time'))
        self.assertEqual(second.time[0] - first.time[0], np.timedelta64(1, 'ms'))

    def test_no_file_reads_none(self):
        self.assertIsNone(patched_reader(ENTRY)(None, 'wave'))


if __name__ == '__main__':
    unittest.main()
