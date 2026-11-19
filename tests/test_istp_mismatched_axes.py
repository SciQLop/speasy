#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Support data that can't be an axis of the data it is attached to.

- The GOES12_EPHEMERIS_SSC master gives GSM_LAT, one value per record, the 3 element DEPEND_1 of XYZ_SM.
- RBSP-A-RBSPICE_LEV-3_TOFXEH files write the NRV Telescope axis of ParticleDir_SM with no record.

CDAWeb's own web service drops such axes; the data itself is fine and must load.
"""

import unittest

import numpy as np
import pycdfpp

from speasy.core.codecs import get_codec

_EPOCH = np.arange('2025-02-28T17:25', '2025-02-28T17:26', np.timedelta64(6, 's'), dtype='datetime64[ns]')


def _make_cdf(data_shape, axes) -> bytes:
    cdf = pycdfpp.CDF()
    cdf.add_variable("Epoch", values=_EPOCH, data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                     attributes={"VAR_TYPE": "support_data"})
    depends = {}
    for index, (name, values) in enumerate(axes, 1):
        cdf.add_variable(name, values=values, is_nrv=True, attributes={"VAR_TYPE": "support_data"})
        depends[f"DEPEND_{index}"] = name
    cdf.add_variable("DATA", values=np.random.random((len(_EPOCH),) + data_shape),
                     attributes={"VAR_TYPE": "data", "DEPEND_0": "Epoch", **depends})
    return bytes(pycdfpp.save(cdf))


def _load(data_shape, axes):
    return get_codec('cdf').load_variable("DATA", file=_make_cdf(data_shape, axes), disable_cache=True)


class MismatchedAxes(unittest.TestCase):

    def test_axis_longer_than_its_dimension_is_dropped(self):
        var = _load((1,), [("cartesian", np.ones((1, 3)))])
        self.assertEqual(len(var), len(_EPOCH))
        self.assertEqual(len(var.axes), 1)

    def test_empty_axis_drops_the_axes_after_it_too(self):
        var = _load((6, 3), [("Telescope", np.ones((0, 6), dtype=np.int8)),
                             ("NumAxisFixed", np.ones((1, 3), dtype=np.int8))])
        self.assertEqual(var.values.shape, (len(_EPOCH), 6, 3))
        self.assertEqual(len(var.axes), 1)

    def test_fitting_axes_are_kept(self):
        var = _load((6, 3), [("Telescope", np.arange(6).reshape(1, 6)),
                             ("NumAxisFixed", np.arange(3).reshape(1, 3))])
        self.assertListEqual([ax.name for ax in var.axes[1:]], ["Telescope", "NumAxisFixed"])


if __name__ == '__main__':
    unittest.main()
