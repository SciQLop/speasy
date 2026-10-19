#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A matrix variable whose LABL_PTR_1 points to a grid of labels, one per element.

3DView's get_transform_matrices CDF stores (n, 3, 3) rotation matrices labelled "xx", "xy", ... "zz".
Those nested labels used to reach SpeasyVariable as columns and crash it.
"""

import unittest

import numpy as np
import pycdfpp

from speasy.core.codecs import get_codec

_EPOCH = np.arange('2015-10-16T00:00', '2015-10-16T03:00', np.timedelta64(1, 'h'), dtype='datetime64[ns]')
_LABELS = [[[f"{row}{col}" for col in "xyz"] for row in "xyz"]]


def _make_matrix_cdf() -> bytes:
    cdf = pycdfpp.CDF()
    cdf.add_variable("Epoch", values=_EPOCH, data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                     attributes={"VAR_TYPE": "support_data"})
    cdf.add_variable("matrixlbl", values=_LABELS, data_type=pycdfpp.DataType.CDF_CHAR,
                     attributes={"VAR_TYPE": "metadata"})
    cdf.add_variable("matrix", values=np.broadcast_to(np.eye(3), (len(_EPOCH), 3, 3)).copy(),
                     attributes={"VAR_TYPE": "data", "DEPEND_0": "Epoch", "LABL_PTR_1": "matrixlbl"})
    return bytes(pycdfpp.save(cdf))


class MatrixWithLabelGrid(unittest.TestCase):

    def test_variable_loads(self):
        var = get_codec('cdf').load_variable("matrix", file=_make_matrix_cdf(), disable_cache=True)
        self.assertIsNotNone(var)
        self.assertEqual(var.values.shape, (len(_EPOCH), 3, 3))


if __name__ == '__main__':
    unittest.main()
