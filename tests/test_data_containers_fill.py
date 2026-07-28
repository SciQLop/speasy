#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the shared ISTP FILLVAL decision used by both plotting and
SpeasyVariable.replace_fillval_by_nan()."""
import unittest

import numpy as np

from speasy.core.data_containers import fill_value_mask


class FillValueMask(unittest.TestCase):
    def test_flags_exact_matches(self):
        mask = fill_value_mask(np.array([1.0, -9999.99, 3.0]), {"FILLVAL": -9999.99})
        np.testing.assert_array_equal(mask, [False, True, False])

    def test_unwraps_single_element_list(self):
        mask = fill_value_mask(np.array([1.0, -9999.99, 3.0]), {"FILLVAL": [-9999.99]})
        np.testing.assert_array_equal(mask, [False, True, False])

    def test_does_not_flag_close_but_different_values(self):
        """FILLVAL is an exact sentinel -- a real reading close to it must survive."""
        mask = fill_value_mask(np.array([1.0, -9999.98, 3.0]), {"FILLVAL": -9999.99})
        np.testing.assert_array_equal(mask, [False, False, False])

    def test_returns_none_when_fillval_absent(self):
        self.assertIsNone(fill_value_mask(np.array([1.0, 2.0, 3.0]), {}))

    def test_flags_nothing_when_fillval_is_nan(self):
        """A NaN sentinel matches nothing, since NaN != NaN -- the data already carries NaN."""
        for fillval in (float("nan"), np.float64("nan"), np.float32("nan")):
            with self.subTest(fillval=type(fillval).__name__):
                mask = fill_value_mask(np.array([1.0, np.nan, 3.0]), {"FILLVAL": [fillval]})
                np.testing.assert_array_equal(mask, [False, False, False])

    def test_warns_and_returns_none_when_fillval_type_is_incompatible(self):
        """Real ISTP files can mis-declare a numeric variable's FILLVAL with a TT2000 attribute
        type (e.g. CDAWeb's ela_att_solution_date); the codec stringifies it while the data
        itself stays numeric."""
        values = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        with self.assertLogs("speasy.core.data_containers", level="WARNING"):
            self.assertIsNone(fill_value_mask(values, {"FILLVAL": "9999-12-31T23:59:59.999999999"}))


if __name__ == "__main__":
    unittest.main()
