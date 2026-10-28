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


if __name__ == '__main__':
    unittest.main()
