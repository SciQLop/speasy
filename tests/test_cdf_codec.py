import unittest
from ddt import ddt, data, unpack
from spwc.common import cdf
from datetime import datetime
from spwc.cache.version import str_to_version
from spwc.common.datetime_range import DateTimeRange
from spwc.common.variable import SpwcVariable

import numpy as np

import tempfile
import shutil
import os


@unittest.skipUnless(cdf.have_cdf, "No cdf support")
class CdfTest(unittest.TestCase):

    def load_simple_var(self):
        cdf_file_name = f"{tempfile.tempdir}/test.cdf"
        if os.path.exists(cdf_file_name):
            os.remove(cdf_file_name)
        cdf_file = cdf.pycdf.CDF(cdf_file_name, '')
        time = [datetime(2000, 10, 1, 1, val) for val in range(60)]
        time_epoch = [t.timestamp() for t in time]
        values = np.random.random_sample(len(time))
        cdf_file['Epoch'] = time
        cdf_file['data'] = values
        cdf_file['data'].attrs['DEPEND_0'] = 'Epoch'
        cdf_file.close()
        var = cdf.load_cdf(cdf_file_name, 'data')
        self.assertTrue(np.all(var.time == time_epoch))
        self.assertTrue(np.all(var.values == values))
        if os.path.exists(cdf_file_name):
            os.remove(cdf_file_name)


if __name__ == '__main__':
    unittest.main()
