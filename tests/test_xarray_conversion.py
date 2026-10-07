"""Tests for xarray <-> SpeasyVariable conversion."""

import sys
import unittest.mock

import astropy.units
import numpy as np
import pandas as pds
import xarray as xr
from ddt import data, ddt

from speasy.products import Dataset, SpeasyVariable
from speasy.products.variable import DataContainer, VariableAxis, VariableTimeAxis

N = 10
TIME = np.datetime64("2020-01-01", "ns") + np.arange(N) * np.timedelta64(1, "s")


def _time_axis(name="time", meta=None):
    return VariableTimeAxis(values=TIME.copy(), name=name, meta=meta or {})


def _var(values, axes=(), columns=None, meta=None, name="var", time_name="time"):
    return SpeasyVariable(axes=[_time_axis(time_name), *axes],
                          values=DataContainer(values=values, meta=meta or {}, name=name),
                          columns=columns)


def scalar():
    return _var(np.arange(N, dtype=float), columns=["v"], meta={"UNITS": "nT"})


def vector():
    return _var(np.ones((N, 3)), columns=["bx", "by", "bz"], meta={"UNITS": "nT", "FILLVAL": -1e31})


def spectrogram():
    energy = VariableAxis(values=np.logspace(1, 3, 4), name="energy", meta={"UNITS": "eV"})
    return _var(np.ones((N, 4)), axes=[energy], name="flux", time_name="Epoch")


def labelled_spectrogram():
    energy = VariableAxis(values=np.logspace(1, 3, 4), name="energy")
    return _var(np.ones((N, 4)), axes=[energy], columns=[f"ch{i}" for i in range(4)])


def time_dependent_spectrogram():
    energy = VariableAxis(values=np.ones((N, 4)), name="energy", is_time_dependent=True)
    return _var(np.ones((N, 4)), axes=[energy])


def sweep():
    frequency = VariableAxis(values=np.arange(N, dtype=float), name="frequency", is_time_dependent=True)
    return _var(np.ones(N), axes=[frequency])


def three_d():
    return _var(np.ones((N, 2, 3)), axes=[VariableAxis(values=np.arange(2.), name="a"),
                                          VariableAxis(values=np.arange(3.), name="b")])


def distribution():
    """MMS FPI / MAVEN SWIA like: fixed angles, time-dependent energy, labels on the first angle."""
    return _var(np.ones((N, 4, 2, 3)),
                axes=[VariableAxis(values=np.arange(4.), name="phi"),
                      VariableAxis(values=np.arange(2.), name="theta"),
                      VariableAxis(values=np.ones((N, 3)), name="energy", is_time_dependent=True)],
                columns=[f"sector{i}" for i in range(4)])


def single_label_3d():
    """MMS HPCA like: one label for a 3D flux."""
    return _var(np.ones((N, 2, 3)), axes=[VariableAxis(values=np.arange(2), name="anode"),
                                          VariableAxis(values=np.arange(3.), name="energy")],
                columns=["H+ Flux"])


def labels_axis():
    """Cluster CIS Status like: an axis of byte string labels next to the columns."""
    labels = [f"Status[{i}]" for i in range(4)]
    return _var(np.ones((N, 4)), axes=[VariableAxis(values=np.array([s.encode() for s in labels]), name="L_Status")],
                columns=labels)


def full_shape_time_dependent_axis():
    """PSP EPI-Lo like: the energy axis has the full data shape."""
    return _var(np.ones((N, 2, 3)), axes=[VariableAxis(values=np.arange(2.), name="look"),
                                          VariableAxis(values=np.ones((N, 2, 3)), name="energy",
                                                       is_time_dependent=True)])


def coordinate_grid():
    """GOLD like: latitude and longitude grids over both spatial dims."""
    return _var(np.ones((N, 2, 3)), axes=[VariableAxis(values=np.ones((2, 3)), name="latitude"),
                                          VariableAxis(values=np.zeros((2, 3)), name="longitude")])


def _spectro_da(dims=("frequency", "time"), time=TIME):
    shape = tuple(N if d == "time" else 4 for d in dims)
    return xr.DataArray(np.ones(shape), dims=dims, name="PSD",
                        coords={"time": time, "frequency": np.arange(4.)})


@ddt
class SpeasyVariableToDataArray(unittest.TestCase):

    def test_dims_and_coords_use_the_axes_names(self):
        da = spectrogram().to_dataarray()
        self.assertEqual(da.dims, ("Epoch", "energy"))
        self.assertEqual(da.name, "flux")
        np.testing.assert_array_equal(da["energy"].values, np.logspace(1, 3, 4))
        self.assertEqual(da["energy"].attrs["units"], "eV")

    def test_time_dependent_axis_is_a_2d_coordinate(self):
        da = time_dependent_spectrogram().to_dataarray()
        self.assertEqual(da["energy"].dims, ("time", "energy"))

    def test_single_column_is_squeezed_and_keeps_its_label(self):
        da = scalar().to_dataarray()
        self.assertEqual(da.dims, ("time",))
        self.assertEqual(da["columns"].item(), "v")

    def test_columns_label_the_second_dim(self):
        da = vector().to_dataarray()
        self.assertEqual(da.dims, ("time", "columns"))
        self.assertEqual(list(da["columns"].values), ["bx", "by", "bz"])

    def test_istp_meta_is_exposed_with_cf_names(self):
        da = vector().to_dataarray()
        self.assertEqual(da.attrs["units"], "nT")
        self.assertEqual(da.attrs["_FillValue"], -1e31)

    def test_unnamed_axis_gets_a_positional_dim_name(self):
        da = _var(np.ones((N, 2)), axes=[VariableAxis(values=np.arange(2.))]).to_dataarray()
        self.assertEqual(da.dims, ("time", "dim_1"))

    def test_sweep_frequency_follows_time(self):
        da = sweep().to_dataarray()
        self.assertEqual(da.dims, ("time",))
        self.assertEqual(da["frequency"].dims, ("time",))

    @data(scalar, vector, spectrogram, labelled_spectrogram, time_dependent_spectrogram, sweep, three_d,
          distribution, single_label_3d, labels_axis, full_shape_time_dependent_axis, coordinate_grid)
    def test_round_trip(self, make):
        var = make()
        back = SpeasyVariable.from_dataarray(var.to_dataarray())
        self.assertEqual(back, var)
        self.assertEqual(back.columns, var.columns)

    def test_missing_xarray_says_how_to_install_it(self):
        var = vector()
        with unittest.mock.patch.dict(sys.modules, {"xarray": None}):
            with self.assertRaisesRegex(ImportError, r"speasy\[xarray\]"):
                var.to_dataarray()


@ddt
class SpeasyVariableFromDataArray(unittest.TestCase):

    @data(("frequency", "time"), ("time", "frequency"))
    def test_time_is_found_by_type_whatever_its_position(self, dims):
        var = SpeasyVariable.from_dataarray(_spectro_da(dims))
        self.assertEqual(var.values.shape, (N, 4))
        self.assertEqual(var.axes[0].name, "time")
        self.assertEqual(var.axes[1].name, "frequency")
        self.assertEqual(var.name, "PSD")
        np.testing.assert_array_equal(var.time, TIME)

    @data("s", "us")
    def test_coarse_time_resolutions_are_converted_to_ns(self, unit):
        var = SpeasyVariable.from_dataarray(_spectro_da(time=TIME.astype(f"datetime64[{unit}]")))
        self.assertEqual(var.time.dtype, np.dtype("datetime64[ns]"))
        np.testing.assert_array_equal(var.time, TIME)

    def test_timezone_aware_time_becomes_naive_utc(self):
        paris = pds.DatetimeIndex(TIME).tz_localize("UTC").tz_convert("Europe/Paris")
        var = SpeasyVariable.from_dataarray(_spectro_da(time=paris))
        np.testing.assert_array_equal(var.time, TIME)

    def test_no_time_dim_says_how_to_fix_it(self):
        da = xr.DataArray(np.ones((3, 4)), dims=("x", "y"))
        with self.assertRaisesRegex(ValueError, "time_dim"):
            SpeasyVariable.from_dataarray(da)

    def test_ambiguous_time_dims_need_time_dim(self):
        da = xr.DataArray(np.ones((N, N)), dims=("start", "stop"), coords={"start": TIME, "stop": TIME})
        with self.assertRaisesRegex(ValueError, "time_dim"):
            SpeasyVariable.from_dataarray(da)
        self.assertEqual(SpeasyVariable.from_dataarray(da, time_dim="stop").axes[0].name, "stop")

    def test_astropy_units_become_strings(self):
        da = _spectro_da()
        da.attrs["units"] = astropy.units.Unit("W m-2 Hz-1")
        self.assertEqual(SpeasyVariable.from_dataarray(da).unit, str(astropy.units.Unit("W m-2 Hz-1")))

    def test_undecoded_fill_value_becomes_fillval(self):
        da = _spectro_da()
        da.attrs["_FillValue"] = -1.
        self.assertEqual(SpeasyVariable.from_dataarray(da).fill_value, -1.)

    def test_dims_without_coordinates_before_an_axis_get_an_index_axis(self):
        da = xr.DataArray(np.ones((N, 2, 4)), dims=("time", "source", "frequency"),
                          coords={"time": TIME, "frequency": np.arange(4.)})
        var = SpeasyVariable.from_dataarray(da)
        self.assertEqual([ax.name for ax in var.axes], ["time", "source", "frequency"])
        np.testing.assert_array_equal(var.axes[1].values, [0, 1])

    def test_string_labels_of_extra_dims_are_kept_as_axes(self):
        da = xr.DataArray(np.ones((N, 2, 4)), dims=("time", "polar", "frequency"),
                          coords={"time": TIME, "polar": ["LL", "RR"], "frequency": np.arange(4.)})
        np.testing.assert_array_equal(SpeasyVariable.from_dataarray(da).axes[1].values, ["LL", "RR"])

    def test_trailing_dims_without_coordinates_get_no_axis(self):
        da = xr.DataArray(np.ones((N, 2, 3)), dims=("time", "x", "y"), coords={"time": TIME})
        self.assertEqual(len(SpeasyVariable.from_dataarray(da).axes), 1)

    def test_time_varying_coordinate_becomes_a_time_dependent_axis(self):
        da = xr.DataArray(np.ones((4, N)), dims=("channel", "time"),
                          coords={"time": TIME, "frequency": (("channel", "time"), np.ones((4, N)))})
        axis = SpeasyVariable.from_dataarray(da).axes[1]
        self.assertEqual(axis.name, "frequency")
        self.assertTrue(axis.is_time_dependent)
        self.assertEqual(axis.values.shape, (N, 4))

    def test_sweeping_frequency_of_1d_data_becomes_a_time_dependent_axis(self):
        da = xr.DataArray(np.ones(N), dims=("time",),
                          coords={"time": TIME, "frequency": ("time", np.arange(N, dtype=float))})
        axis = SpeasyVariable.from_dataarray(da).axes[1]
        self.assertTrue(axis.is_time_dependent)
        self.assertEqual(axis.values.shape, (N,))

    def test_string_labels_of_a_2d_array_become_columns(self):
        da = xr.DataArray(np.ones((N, 3)), dims=("time", "component"),
                          coords={"time": TIME, "component": ["x", "y", "z"]})
        var = SpeasyVariable.from_dataarray(da)
        self.assertEqual(var.columns, ["x", "y", "z"])
        self.assertEqual(len(var.axes), 1)


class DatasetFromXarray(unittest.TestCase):

    def test_variables_with_time_are_converted_others_skipped(self):
        ds = xr.Dataset({"PSD_V2": (("frequency", "time"), np.ones((4, N))),
                         "PSD_SFU": (("frequency", "time"), np.ones((4, N))),
                         "calibration": ("frequency", np.ones(4))},
                        coords={"time": TIME, "frequency": np.arange(4.)},
                        attrs={"title": "maser like"})
        dataset = Dataset.from_xarray(ds, name="rpw")
        self.assertEqual(sorted(dataset.variables), ["PSD_SFU", "PSD_V2"])
        self.assertEqual(dataset.name, "rpw")
        self.assertEqual(dataset.meta, {"title": "maser like"})
        self.assertEqual(dataset["PSD_V2"].values.shape, (N, 4))


if __name__ == "__main__":
    unittest.main()
