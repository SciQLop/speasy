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


_MAP_TIME = np.array(["2018-10-05", "2018-10-06"], dtype="datetime64[ns]")


def _map_plot(display_type="map_image>THUMBSIZE>166>MAP_PROJ>7>SMOOTH>x=latitude,y=longitude",
              time_dependent_grids=False):
    """A GOLD_L2_ON2 shaped variable: latitude and longitude grids over the two spatial dims."""
    latitude = np.array([[0., 0., 0.], [1., 1., 1.]])
    longitude = np.array([[0., 1., 2.], [0., 1., 2.]])
    if time_dependent_grids:
        latitude = np.stack([latitude, latitude])
        longitude = np.stack([longitude, longitude])
    return Plot(
        axes=[VariableTimeAxis(values=_MAP_TIME),
              VariableAxis(values=latitude, name="latitude", is_time_dependent=time_dependent_grids),
              VariableAxis(values=longitude, name="longitude", is_time_dependent=time_dependent_grids)],
        values=DataContainer(values=np.arange(12.).reshape(2, 2, 3),
                             meta={"DISPLAY_TYPE": display_type}, name="on2"),
        columns_names=["value"],
    )


class DisplayTypeDispatch(unittest.TestCase):
    """DISPLAY_TYPE was compared whole, so anything carrying modifiers fell through to a line plot.

    1012 CDAWeb parameters spell it 'spectrogram>y=...,z=...' rather than plain 'spectrogram'.
    """

    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_plain_spectrogram_is_a_colormap(self):
        ax = _colormap_plot(values_meta={"DISPLAY_TYPE": "spectrogram"})()
        self.assertEqual(len(ax.collections), 1)

    def test_spectrogram_with_modifiers_is_a_colormap(self):
        ax = _colormap_plot(
            values_meta={"DISPLAY_TYPE": "spectrogram>y=Center_Scan, z=MEDUSA_Electron(1,*)"})()
        self.assertEqual(len(ax.collections), 1)

    def test_time_series_is_a_line(self):
        ax = _line_plot(values_meta={"DISPLAY_TYPE": "time_series"})()
        self.assertEqual(len(ax.get_lines()), 1)

    def test_no_display_type_is_a_line(self):
        ax = _line_plot()()
        self.assertEqual(len(ax.get_lines()), 1)

    def test_map_image_is_a_colormap(self):
        ax = _map_plot()()
        self.assertEqual(len(ax.collections), 1)


class ColormapOverCoordinateGrids(unittest.TestCase):
    """A map is a colormap whose axes happen to be grids, not a plot type of its own."""
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_uses_the_coordinate_grids_named_by_the_hint(self):
        # CDAWeb spells GOLD's hint 'x=latitude,y=longitude', so the axes are not in array order
        ax = _map_plot().colormap()
        self.assertEqual(ax.get_xlabel(), "latitude")
        self.assertEqual(ax.get_ylabel(), "longitude")

    def test_falls_back_to_array_order_without_a_hint(self):
        ax = _map_plot(display_type="map_image").colormap()
        self.assertEqual(ax.get_xlabel(), "longitude")
        self.assertEqual(ax.get_ylabel(), "latitude")

    def test_plots_one_time_step(self):
        ax = _map_plot().colormap(time_index=1)
        mesh = ax.collections[0]
        self.assertEqual(mesh.get_array().size, 6)

    def test_grids_with_holes_still_draw(self):
        # 37% of GOLD_L2_ON2's grid is NaN, the cells looking off the Earth's disk, and
        # pcolormesh refuses non-finite coordinates outright
        plot = _map_plot()
        plot.axes[1].values[0, 0] = np.nan
        plot.axes[2].values[0, 0] = np.nan
        ax = plot.colormap()
        self.assertEqual(len(ax.collections), 1)

    def test_record_varying_grids_are_indexed_by_time_too(self):
        ax = _map_plot(time_dependent_grids=True).colormap(time_index=1)
        self.assertEqual(len(ax.collections), 1)


class ColormapRefusesMoreThanTwoDimensions(unittest.TestCase):
    def setUp(self):
        self.addCleanup(plt.close, "all")

    def test_one_grid_among_plain_axes_is_not_a_map(self):
        # PSP_ISOIS-EPILO_L2-PE has a plain look direction axis and an energy grid over every
        # dimension. Only one of its two spatial dimensions has a coordinate, so there is nothing
        # to spread a map over and it must ask for a reduction like any other 3D spectrogram.
        plot = Plot(
            axes=[VariableTimeAxis(values=_MAP_TIME),
                  VariableAxis(values=np.arange(2.), name="look_direction"),
                  VariableAxis(values=np.random.random((2, 2, 3)), name="energy",
                               is_time_dependent=True)],
            values=DataContainer(values=np.arange(12.).reshape(2, 2, 3),
                                 meta={"DISPLAY_TYPE": "spectrogram"}, name="counts"),
            columns_names=["value"])
        with self.assertRaises(ValueError) as e:
            plot.colormap()
        self.assertIn("3 dimensions", str(e.exception))

    def test_error_names_the_way_out(self):
        # PSP_ISOIS-EPILO_L2-PE is a 3D spectrogram; matplotlib used to answer with an opaque
        # "Dimensions of C (3, 5, 6) should be one smaller than X(6) and Y(5)"
        plot = Plot(
            axes=[VariableTimeAxis(values=_MAP_TIME),
                  VariableAxis(values=np.arange(2.), name="look_direction"),
                  VariableAxis(values=np.arange(3.), name="energy")],
            values=DataContainer(values=np.arange(12.).reshape(2, 2, 3),
                                 meta={"DISPLAY_TYPE": "spectrogram"}, name="counts"),
            columns_names=["value"])
        with self.assertRaises(ValueError) as e:
            plot.colormap()
        self.assertIn("3 dimensions", str(e.exception))
        self.assertIn("axis=", str(e.exception))


if __name__ == "__main__":
    unittest.main()
