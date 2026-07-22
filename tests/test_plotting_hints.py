#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests that speasy.plotting.Plot wires ISTP metadata hints into plot defaults,
with explicit kwargs always taking precedence over a hint."""
import unittest

import matplotlib.pyplot as plt
import numpy as np

from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.plotting import Plot

_TIME = np.array(["2020-01-01", "2020-01-02", "2020-01-03"], dtype="datetime64[ns]")


def _line_plot(values_meta=None, values_array=None):
    values = np.array([1.0, 2.0, 3.0]) if values_array is None else values_array
    return Plot(
        axes=[VariableTimeAxis(values=_TIME)],
        values=DataContainer(values=values, meta=values_meta or {}, name="raw_name"),
        columns_names=["value"],
    )


class LineHints(unittest.TestCase):
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_uses_scaletyp_hint_for_logy_when_not_explicit(self):
        ax = _line_plot(values_meta={"SCALETYP": "log"}).line()
        self.assertEqual(ax.get_yscale(), "log")

    def test_explicit_logy_overrides_scaletyp_hint(self):
        ax = _line_plot(values_meta={"SCALETYP": "log"}).line(logy=False)
        self.assertEqual(ax.get_yscale(), "linear")

    def test_defaults_to_linear_when_no_hint_and_no_kwarg(self):
        ax = _line_plot().line()
        self.assertEqual(ax.get_yscale(), "linear")

    def test_uses_lablaxis_hint_for_yaxis_label_when_not_explicit(self):
        ax = _line_plot(values_meta={"LABLAXIS": "Foo"}).line(units="nT")
        self.assertEqual(ax.get_ylabel(), "Foo (nT)")

    def test_explicit_yaxis_label_overrides_lablaxis_hint(self):
        ax = _line_plot(values_meta={"LABLAXIS": "Foo"}).line(units="nT", yaxis_label="Bar")
        self.assertEqual(ax.get_ylabel(), "Bar (nT)")

    def test_masks_fillval_by_default(self):
        ax = _line_plot(values_meta={"FILLVAL": -999.0},
                        values_array=np.array([1.0, -999.0, 3.0])).line()
        ydata = ax.get_lines()[0].get_ydata()
        self.assertTrue(np.isnan(ydata[1]))

    def test_mask_fillval_false_disables_masking(self):
        ax = _line_plot(values_meta={"FILLVAL": -999.0},
                        values_array=np.array([1.0, -999.0, 3.0])).line(mask_fillval=False)
        ydata = ax.get_lines()[0].get_ydata()
        self.assertEqual(ydata[1], -999.0)


if __name__ == "__main__":
    unittest.main()
