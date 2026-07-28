#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for ISTP metadata -> plot hint mapping."""
import unittest

import numpy as np

from speasy.plotting.istp_hints import (
    is_log_scale,
    label_from_meta,
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


if __name__ == "__main__":
    unittest.main()
