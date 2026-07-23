#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests that speasy.plotting.Plot wires ISTP metadata hints into plot defaults,
with explicit kwargs always taking precedence over a hint."""
import unittest

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

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


def _colormap_plot(values_meta=None, y_axis_meta=None, values_array=None):
    y = np.array([10.0, 20.0])
    values = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]) if values_array is None else values_array
    return Plot(
        axes=[
            VariableTimeAxis(values=_TIME),
            VariableAxis(values=y, meta=y_axis_meta or {}),
        ],
        values=DataContainer(values=values, meta=values_meta or {}, name="raw_name"),
        columns_names=["value"],
    )


class ColormapHints(unittest.TestCase):
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_uses_scaletyp_hint_for_logz_when_not_explicit(self):
        ax = _colormap_plot(values_meta={"SCALETYP": "linear"}).colormap()
        mesh = ax.collections[0]
        self.assertNotIsInstance(mesh.norm, LogNorm)

    def test_explicit_logz_overrides_scaletyp_hint(self):
        ax = _colormap_plot(values_meta={"SCALETYP": "log"}).colormap(logz=False)
        mesh = ax.collections[0]
        self.assertNotIsInstance(mesh.norm, LogNorm)

    def test_defaults_to_log_when_no_hint_and_no_kwarg(self):
        ax = _colormap_plot().colormap()
        mesh = ax.collections[0]
        self.assertIsInstance(mesh.norm, LogNorm)

    def test_uses_scaletyp_hint_for_logy_when_not_explicit(self):
        ax = _colormap_plot(y_axis_meta={"SCALETYP": "linear"}).colormap(logz=False)
        self.assertEqual(ax.get_yscale(), "linear")

    def test_masks_fillval_in_z_by_default(self):
        values = np.array([[1.0, 2.0], [3.0, -999.0], [5.0, 6.0]])
        ax = _colormap_plot(values_meta={"FILLVAL": -999.0}, values_array=values).colormap(logz=False)
        mesh = ax.collections[0]
        self.assertTrue(np.ma.getmaskarray(mesh.get_array()).any())

    def test_uses_lablaxis_hint_for_yaxis_and_zaxis_labels_when_not_explicit(self):
        ax = _colormap_plot(
            y_axis_meta={"LABLAXIS": "Energy"},
            values_meta={"LABLAXIS": "Particle Energy Flux"},
        ).colormap(yaxis_units="eV", zaxis_units="1/(cm2 s sr keV)", logz=False)
        self.assertEqual(ax.get_ylabel(), "Energy (eV)")
        colorbar_ax = ax.figure.axes[-1]
        self.assertEqual(colorbar_ax.get_ylabel(), "Particle Energy Flux (1/(cm2 s sr keV))")

    def test_explicit_logy_overrides_scaletyp_hint(self):
        ax = _colormap_plot(y_axis_meta={"SCALETYP": "log"}).colormap(logy=False, logz=False)
        self.assertEqual(ax.get_yscale(), "linear")

    def test_mask_fillval_false_disables_masking(self):
        values = np.array([[1.0, 2.0], [3.0, -999.0], [5.0, 6.0]])
        ax = _colormap_plot(values_meta={"FILLVAL": -999.0}, values_array=values).colormap(
            logz=False, mask_fillval=False)
        mesh = ax.collections[0]
        self.assertFalse(np.ma.getmaskarray(mesh.get_array()).any())

    def test_all_fillval_slice_does_not_crash(self):
        """A slice that's entirely FILLVAL masks to all-NaN; vmin/vmax must not end up NaN
        (LogNorm raises "Invalid vmin or vmax" on NaN bounds, so this must use the default
        logz=True to reproduce)."""
        values = np.full((3, 2), -999.0)
        ax = _colormap_plot(values_meta={"FILLVAL": -999.0}, values_array=values).colormap()
        mesh = ax.collections[0]
        self.assertTrue(np.ma.getmaskarray(mesh.get_array()).all())


if __name__ == "__main__":
    unittest.main()
