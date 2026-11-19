#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Variables the master CDF lists but a data file does not hold.

The MMS EPD-EIS masters list every variable any file version ever held (the P4, P5 and P6 sets,
variables "available beginning on 2025/01/06"...), while each data file only holds its own subset.
Such a file has no data for the variable, it must load as nothing rather than raise a KeyError.
"""

import unittest

import numpy as np
import pycdfpp

from speasy.core.codecs import get_codec

_EPOCH = np.arange('2025-02-28T17:25', '2025-02-28T17:26', np.timedelta64(6, 's'), dtype='datetime64[ns]')


def _make_cdf(variables) -> bytes:
    cdf = pycdfpp.CDF()
    cdf.add_variable("Epoch", values=_EPOCH, data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                     attributes={"VAR_TYPE": "support_data"})
    for name in variables:
        cdf.add_variable(name, values=np.random.random(len(_EPOCH)),
                         attributes={"VAR_TYPE": "data", "DEPEND_0": "Epoch"})
    return bytes(pycdfpp.save(cdf))


class MasterOnlyVariables(unittest.TestCase):

    def test_variable_missing_from_the_data_file_loads_as_none(self):
        var = get_codec('cdf').load_variable("P5_counts", file=_make_cdf(["P6_counts"]),
                                             master_cdf_url=_make_cdf(["P5_counts", "P6_counts"]),
                                             disable_cache=True)
        self.assertIsNone(var)

    def test_variable_present_in_the_data_file_still_loads(self):
        var = get_codec('cdf').load_variable("P6_counts", file=_make_cdf(["P6_counts"]),
                                             master_cdf_url=_make_cdf(["P5_counts", "P6_counts"]),
                                             disable_cache=True)
        self.assertEqual(len(var), len(_EPOCH))


if __name__ == '__main__':
    unittest.main()
