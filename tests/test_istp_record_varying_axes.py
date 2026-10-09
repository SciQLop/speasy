#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Record-varying support data whose master CDF forgot DEPEND_0.

SOLO_L2_SWA-EAS-PAD-DEF ships SWA_EAS_ELEVATION and SWA_EAS_ENERGY with one row per record and
DEPEND_0 = EPOCH in the data files, but its master drops that DEPEND_0. Attributes are read from the
master, so these axes looked time independent and the variable failed its shape check
(https://github.com/SciQLop/speasy/issues/399).
"""

import unittest

import numpy as np
import pycdfpp
from pyistp.support_data_variable import SupportDataVariable

from speasy.core.codecs import get_codec
from speasy.core.codecs.bundled_codecs.istp import _is_time_dependent

_N, _ELEVATION, _ENERGY, _AZIMUTH = 10, 2, 4, 3
_EPOCH = np.arange('2025-02-28T17:25', '2025-02-28T17:26', np.timedelta64(6, 's'), dtype='datetime64[ns]')


def _make_cdf(n_records: int, axes_depend_on_epoch: bool) -> bytes:
    axis_attributes = {"VAR_TYPE": "support_data"}
    if axes_depend_on_epoch:
        axis_attributes["DEPEND_0"] = "EPOCH"
    cdf = pycdfpp.CDF()
    cdf.add_variable("EPOCH", values=_EPOCH[:n_records], data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                     attributes={"VAR_TYPE": "support_data"})
    cdf.add_variable("ELEVATION", values=np.random.random((n_records, _ELEVATION)), attributes=axis_attributes)
    cdf.add_variable("ENERGY", values=np.random.random((n_records, _ENERGY)), attributes=axis_attributes)
    cdf.add_variable("AZIMUTH", values=np.random.random((1, _AZIMUTH)), is_nrv=True,
                     attributes={"VAR_TYPE": "support_data"})
    cdf.add_variable("PAD", values=np.random.random((n_records, _ELEVATION, _ENERGY, _AZIMUTH)),
                     attributes={"VAR_TYPE": "data", "DEPEND_0": "EPOCH", "DEPEND_1": "ELEVATION",
                                 "DEPEND_2": "ENERGY", "DEPEND_3": "AZIMUTH"})
    return bytes(pycdfpp.save(cdf))


def _load_with_master_lacking_depend_0():
    return get_codec('cdf').load_variable("PAD", file=_make_cdf(_N, axes_depend_on_epoch=True),
                                          master_cdf_url=_make_cdf(0, axes_depend_on_epoch=False),
                                          disable_cache=True)


class RecordVaryingAxesWithoutDepend0(unittest.TestCase):

    def test_variable_loads(self):
        var = _load_with_master_lacking_depend_0()
        self.assertIsNotNone(var)
        self.assertEqual(var.values.shape, (_N, _ELEVATION, _ENERGY, _AZIMUTH))

    def test_record_varying_axes_are_time_dependent(self):
        var = _load_with_master_lacking_depend_0()
        self.assertListEqual([ax.is_time_dependent for ax in var.axes[1:]], [True, True, False])

    def test_time_dependent_axes_follow_time_slices(self):
        var = _load_with_master_lacking_depend_0()[2:5]
        self.assertListEqual([ax.shape for ax in var.axes[1:]], [(3, _ELEVATION), (3, _ENERGY), (_AZIMUTH,)])

    def test_an_explicit_depend_0_on_another_epoch_is_not_overridden_by_the_record_count(self):
        axis = SupportDataVariable(name="ENERGY", values=np.random.random((_N, _ENERGY)),
                                   attributes={"DEPEND_0": "OTHER_EPOCH"}, is_nrv=False, cdf_type=None)
        self.assertFalse(_is_time_dependent(axis, "EPOCH", _N))


if __name__ == '__main__':
    unittest.main()
