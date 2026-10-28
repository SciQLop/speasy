import os
import unittest

import numpy as np
import pycdfpp
import speasy as spz
from speasy.core.any_files import any_loc_open

ARCHIVE = 'https://cdaweb.gsfc.nasa.gov/pub/data/psp/fields/l2'


def _raw_flat(url: str, time: str, variable: str):
    with any_loc_open(url, cache_remote_files=True) as f:
        cdf = pycdfpp.load(f.read())
    return pycdfpp.to_datetime64(cdf[time]).ravel(), cdf[variable].values.ravel()


def _step_error_ns(var, snapshots: int, rates=262137.5) -> float:
    """Worst deviation from 1e9/rate ns between consecutive samples of a snapshot; the E offsets are float32,
    which quantises them to 1 ns, so consecutive differences can be off by 2 ns."""
    steps = np.diff(var.time.reshape(snapshots, -1), axis=1).astype('int64')
    return np.abs(steps - 1e9 / np.reshape(rates, (-1, 1))).max()


class PspFieldsPatches(unittest.TestCase):
    def test_psp_dbm_vac_matches_raw(self):
        raw_time, raw_values = _raw_flat(
            f"{ARCHIVE}/dfb_dbm_vac/2020/psp_fld_l2_dfb_dbm_vac_2020052718_v03.cdf",
            'psp_fld_l2_dfb_dbm_vac_time_series_TT2000', 'psp_fld_l2_dfb_dbm_vac1')
        var = spz.get_data('cda/PSP_FLD_L2_DFB_DBM_VAC/psp_fld_l2_dfb_dbm_vac1_f',
                           '2020-05-27T18:00', '2020-05-27T23:59', method='FILE')
        self.assertEqual(len(var), len(raw_time))
        self.assertEqual(np.diff(var.time[:2])[0], np.timedelta64(6666, 'ns'))
        np.testing.assert_array_equal(var.time, raw_time)
        np.testing.assert_array_equal(var.values[:, 0], raw_values)

    def test_psp_tds_2023_not_empty(self):
        var = spz.get_data('cda/PSP_FLD_L2_TDS_WF/PSP_FLD_L2_TDS_WF_Burst_Time_Series_V2_Engineering_mV_f',
                           '2023-01-02', '2023-01-03', method='FILE')
        self.assertGreater(len(var), 0)


SOLO_RPW = 'https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/rpw/science/l2'


def _raw_values(url: str, variable: str):
    with any_loc_open(url, cache_remote_files=True) as f:
        return pycdfpp.load(f.read())[variable].values


class SoloTdsSnapshots(unittest.TestCase):
    def test_solo_tds_rswf_e(self):
        var = spz.get_data('cda/SOLO_L2_RPW-TDS-SURV-RSWF-E/WAVEFORM_DATA', '2021-01-01', '2021-01-02')
        self.assertEqual(var.values.shape, (285 * 4096, 3))
        self.assertLessEqual(_step_error_ns(var, 285), 2.0)

    def test_solo_tds_rswf_b(self):
        var = spz.get_data('cda/SOLO_L2_RPW-TDS-SURV-RSWF-B/B', '2021-01-01', '2021-01-02')
        self.assertEqual(var.values.shape, (285 * 4096, 1))
        file_rates = _raw_values(f"{SOLO_RPW}/tds-surv-rswf-b/2021/solo_l2_rpw-tds-surv-rswf-b_20210101_v06.cdf",
                                 'SAMPLING_RATE').astype('float64')
        self.assertLessEqual(_step_error_ns(var, 285, file_rates), 1.0)

    def test_solo_tds_tswf_b(self):
        var = spz.get_data('cda/SOLO_L2_RPW-TDS-SURV-TSWF-B/B', '2021-01-01', '2021-01-02')
        self.assertEqual(var.values.shape, (239 * 16384, 1))

    @unittest.skipUnless(os.environ.get('SPEASY_LONG_TESTS'), "the 2021-01-01 TSWF-E file is 71 MB")
    def test_solo_tds_tswf_e(self):
        var = spz.get_data('cda/SOLO_L2_RPW-TDS-SURV-TSWF-E/WAVEFORM_DATA', '2021-01-01', '2021-01-02')
        self.assertEqual(var.values.shape, (239 * 16384, 3))


LFR_RATES_HZ = {'F0': 24576, 'F1': 4096, 'F2': 256}
LFR_SAMPLES = 2048
IN_DAY_SNAPSHOTS = 1944  # a 1945th snapshot of the file starts on 2021-01-02


def _snapshot_centers(var, rate_hz: int) -> np.ndarray:
    starts = var.time.reshape(-1, LFR_SAMPLES)[:, 0]
    return starts + np.timedelta64(round((LFR_SAMPLES - 1) / 2 * 1e9 / rate_hz), 'ns')


def _nearest_offsets_ns(centers: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return np.array([np.abs(reference - c).min() for c in centers]).astype('timedelta64[ns]').astype('int64')


@unittest.skipUnless(os.environ.get('SPEASY_LONG_TESTS'), "the 2021-01-01 LFR SWF files are 159 MB and 254 MB")
class SoloLfrSnapshots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vdc = {f: spz.get_data(f'cda/SOLO_L2_RPW-LFR-SURV-SWF-E/VDC_{f}', '2021-01-01', '2021-01-02')
                   for f in LFR_RATES_HZ}

    def test_lfr_rates_share_centers(self):
        centers = {f: _snapshot_centers(v, LFR_RATES_HZ[f]) for f, v in self.vdc.items()}
        for faster in ('F0', 'F1'):
            offsets = _nearest_offsets_ns(centers['F2'], centers[faster])
            self.assertGreaterEqual(np.mean(np.abs(offsets) < 10e6), 0.99, faster)

    def test_lfr_f2_spacing(self):
        steps = np.diff(self.vdc['F2'].time.reshape(-1, LFR_SAMPLES), axis=1).astype('int64')
        self.assertLessEqual(np.abs(steps - 1e9 / 256).max(), 1.0)

    def test_lfr_swf_e_shapes(self):
        self.assertEqual({f: v.values.shape for f, v in self.vdc.items()}, {f: (IN_DAY_SNAPSHOTS * LFR_SAMPLES, 3) for f in self.vdc})

    def test_lfr_swf_b_is_channel_first(self):
        var = spz.get_data('cda/SOLO_L2_RPW-LFR-SURV-SWF-B/B_F2', '2021-01-01', '2021-01-02')
        self.assertEqual(var.values.shape, (IN_DAY_SNAPSHOTS * LFR_SAMPLES, 3))
        self.assertLessEqual(np.abs(np.diff(var.time.reshape(-1, LFR_SAMPLES), axis=1).astype('int64')
                                    - 1e9 / 256).max(), 1.0)


if __name__ == '__main__':
    unittest.main()
