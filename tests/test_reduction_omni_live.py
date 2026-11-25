"""numpy reductions on real data: a 3D ion distribution's omni spectrum, built as the documentation shows (numpy plus
speasy.signal.reduction.dimension), gives back the mission's official one.

MMS FPI averages over solid angle: a mean over phi, then a mean over theta weighted by each band's solid angle, which
the caller computes from the theta axis and its ISTP deltas. Cluster CIS (HIA and CODIF) takes the plain mean of its
angle bins.
"""
import os
import unittest

import numpy as np

import speasy as spz
from speasy.signal.reduction import dimension

PROTON_MASS = 1.67262192e-27  # kg
EV = 1.602176634e-19  # J


def _energy_flux_from_psd(psd: np.ndarray, energy_ev: np.ndarray) -> np.ndarray:
    """Differential energy flux f·v⁴/2, in 1/(cm² s sr), from a phase space density in s³/cm⁶ on an energy axis in
    eV."""
    v_cm_s = np.sqrt(2 * energy_ev * EV / PROTON_MASS) * 100.
    return psd * v_cm_s ** 4 / 2


def _solid_angle_weights(theta) -> np.ndarray:
    """cos θ₁ - cos θ₂ for each colatitude band, from the axis values and their deltas, in degrees."""
    lower = np.radians(theta.values - theta.delta_minus)
    upper = np.radians(theta.values + theta.delta_plus)
    return np.cos(lower) - np.cos(upper)


def _ratio_percentiles(values: np.ndarray, time: np.ndarray, omni):
    common, i, j = np.intersect1d(time, omni.time, return_indices=True)
    a, b = np.asarray(values, dtype=float)[i], np.array(omni.values, dtype=float)[j]
    good = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
    ratio = a[good] / b[good]
    assert ratio.size > 100, f"only {ratio.size} comparable bins"
    return np.percentile(ratio, [16, 50, 84])


def _flux_ratio_percentiles(reduced, omni):
    energy = np.asarray(reduced.axes[1].values, dtype=float)
    return _ratio_percentiles(_energy_flux_from_psd(np.asarray(reduced.values, dtype=float), energy), reduced.time,
                              omni)


def _mean_over(var, *names, weights=None):
    """The mean over the named axes, fill values ignored, as the documentation shows."""
    var = var.replace_fillval_by_nan()
    axis = tuple(dimension(var, name) for name in names)
    return np.nanmean(var, axis=axis) if weights is None else np.average(var, axis=axis[0], weights=weights)


def _mms(start, stop):
    dist = spz.get_data('cda/MMS1_FPI_FAST_L2_DIS-DIST/mms1_dis_dist_fast', start, stop)
    omni = spz.get_data('cda/MMS1_FPI_FAST_L2_DIS-MOMS/mms1_dis_energyspectr_omni_fast', start, stop)
    return dist, omni


@unittest.skipUnless('SPEASY_LONG_TESTS' in os.environ, "downloads MMS and Cluster distributions")
class OmniSpectraFromDistributions(unittest.TestCase):
    def test_mms_fpi_dis_is_a_solid_angle_average(self):
        for start, stop in (('2015-10-16T13:00', '2015-10-16T13:05'), ('2017-07-11T22:30', '2017-07-11T22:33')):
            dist, omni = _mms(start, stop)
            weights = _solid_angle_weights(dist.axes[2])
            reduced = _mean_over(_mean_over(dist, 'phi'), 'theta', weights=weights)
            p16, p50, p84 = _flux_ratio_percentiles(reduced, omni)
            self.assertAlmostEqual(p50, 1., delta=0.002)
            self.assertLess(p84 - p16, 0.002)

    def test_mms_fpi_dis_plain_mean_does_not_match(self):
        dist, omni = _mms('2015-10-16T13:00', '2015-10-16T13:05')
        reduced = _mean_over(dist, 'phi', 'theta')
        self.assertGreater(abs(_flux_ratio_percentiles(reduced, omni)[1] - 1.), 0.02)

    def test_cluster_cis_is_a_plain_mean(self):
        pairs = (('C1_CP_CIS-HIA_HS_MAG_IONS_PEF/ions_3d__C1_CP_CIS_HIA_HS_MAG_IONS_PEF',
                  'C1_CP_CIS-HIA_HS_1D_PEF/flux__C1_CP_CIS_HIA_HS_1D_PEF'),
                 ('C4_CP_CIS-CODIF_HS_H1_PEF/ions_3d__C4_CP_CIS_CODIF_HS_H1_PEF',
                  'C4_CP_CIS-CODIF_H1_1D_PEF/flux__C4_CP_CIS_CODIF_H1_1D_PEF'))
        for dist_id, omni_id in pairs:
            for start, stop in (('2003-02-02T10:00', '2003-02-02T10:10'), ('2004-03-10T12:00', '2004-03-10T12:10')):
                with self.subTest(dist_id=dist_id, start=start):
                    dist = spz.get_data(f'cda/{dist_id}', start, stop)
                    omni = spz.get_data(f'cda/{omni_id}', start, stop)
                    reduced = _mean_over(dist, 'theta', 'phi')
                    p16, p50, p84 = _ratio_percentiles(reduced.values, reduced.time, omni)
                    self.assertAlmostEqual(p50, 1., delta=1e-4)
                    self.assertLess(p84 - p16, 1e-4)


if __name__ == '__main__':
    unittest.main()
