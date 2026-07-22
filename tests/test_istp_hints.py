#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for ISTP metadata -> plot hint mapping."""
import unittest

import numpy as np

from speasy.plotting.istp_hints import (
    is_log_scale,
    label_from_meta,
    mask_fill_values,
    scale_type_from_meta,
)


class ScaleTypeFromMeta(unittest.TestCase):
    def test_reads_scaletyp(self):
        self.assertEqual(scale_type_from_meta({"SCALETYP": "log"}), "log")
        self.assertEqual(scale_type_from_meta({"SCALETYP": "linear"}), "linear")

    def test_unwraps_single_element_list(self):
        self.assertEqual(scale_type_from_meta({"SCALETYP": ["log"]}), "log")

    def test_is_case_insensitive(self):
        self.assertEqual(scale_type_from_meta({"SCALETYP": "LOG"}), "log")

    def test_returns_none_when_absent(self):
        self.assertIsNone(scale_type_from_meta({}))

    def test_returns_none_on_unrecognized_value(self):
        self.assertIsNone(scale_type_from_meta({"SCALETYP": "banana"}))


class IsLogScale(unittest.TestCase):
    def test_true_for_log(self):
        self.assertIs(is_log_scale({"SCALETYP": "log"}), True)

    def test_false_for_linear(self):
        self.assertIs(is_log_scale({"SCALETYP": "linear"}), False)

    def test_none_when_absent(self):
        self.assertIsNone(is_log_scale({}))


class LabelFromMeta(unittest.TestCase):
    def test_reads_lablaxis(self):
        self.assertEqual(label_from_meta({"LABLAXIS": "Particle Energy Flux"}), "Particle Energy Flux")

    def test_unwraps_single_element_list(self):
        self.assertEqual(label_from_meta({"LABLAXIS": ["Bx"]}), "Bx")

    def test_returns_none_when_absent(self):
        self.assertIsNone(label_from_meta({}))


class MaskFillValues(unittest.TestCase):
    def test_replaces_exact_matches_with_nan(self):
        values = np.array([1.0, -9999.99, 3.0])
        result = mask_fill_values(values, {"FILLVAL": -9999.99})
        self.assertTrue(np.isnan(result[1]))
        self.assertEqual(result[0], 1.0)
        self.assertEqual(result[2], 3.0)

    def test_unwraps_single_element_list(self):
        values = np.array([1.0, -9999.99, 3.0])
        result = mask_fill_values(values, {"FILLVAL": [-9999.99]})
        self.assertTrue(np.isnan(result[1]))

    def test_does_not_touch_close_but_different_values(self):
        """FILLVAL is an exact sentinel -- a real reading close to it must survive."""
        values = np.array([1.0, -9999.98, 3.0])
        result = mask_fill_values(values, {"FILLVAL": -9999.99})
        self.assertEqual(result[1], -9999.98)

    def test_is_noop_when_fillval_absent(self):
        values = np.array([1.0, 2.0, 3.0])
        result = mask_fill_values(values, {})
        np.testing.assert_array_equal(result, values)

    def test_is_noop_when_fillval_is_nan(self):
        """Some providers (e.g. AMDA) report FILLVAL: [nan] -- data already uses NaN directly."""
        values = np.array([1.0, np.nan, 3.0])
        result = mask_fill_values(values, {"FILLVAL": [float("nan")]})
        self.assertTrue(np.isnan(result[1]))
        self.assertEqual(result[0], 1.0)

    def test_does_not_mutate_input(self):
        values = np.array([1.0, -9999.99, 3.0])
        mask_fill_values(values, {"FILLVAL": -9999.99})
        self.assertEqual(values[1], -9999.99)


if __name__ == "__main__":
    unittest.main()
