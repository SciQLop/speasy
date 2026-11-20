import os
import tempfile
import unittest

import numpy as np
import pycdfpp

from speasy.core.cdf.inventory_extractor import extract_from_master


def _master_with_a_virtual_variable(path):
    cdf = pycdfpp.CDF()
    time = np.arange("2022-01-01T00:00:00", "2022-01-01T00:00:10", dtype="datetime64[s]").astype("datetime64[ns]")
    cdf.add_variable("Epoch", values=pycdfpp.to_tt2000(time), data_type=pycdfpp.DataType.CDF_TIME_TT2000,
                     attributes={"VAR_TYPE": ["support_data"]})
    cdf.add_variable("B", values=np.ones((10, 3)), attributes={"VAR_TYPE": ["data"], "DEPEND_0": ["Epoch"]})
    # CDAWeb computes this one on request: it is in the master but never in a data file
    cdf.add_variable("B_clean", values=np.ones((10, 3)),
                     attributes={"VAR_TYPE": ["data"], "DEPEND_0": ["Epoch"], "VIRTUAL": ["TRUE"],
                                 "FUNCT": ["apply_qflag"], "COMPONENT_0": ["B"]})
    pycdfpp.save(cdf, path)


class ExtractFromMaster(unittest.TestCase):
    def test_virtual_variables_are_not_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "master.cdf")
            _master_with_a_virtual_variable(path)
            parameters, _ = extract_from_master(path, provider="archive", disable_cache=True)
        self.assertEqual([p.spz_name() for p in parameters], ["B"])


if __name__ == '__main__':
    unittest.main()
