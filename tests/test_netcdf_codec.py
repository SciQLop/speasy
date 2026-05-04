#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the ISTP NetCDF codec (speasy.core.codecs.bundled_codecs.istp_netcdf)."""

import os
import unittest
import numpy as np
import pytest

try:
    import netCDF4
except ImportError:
    pytest.skip("netCDF4 not installed", allow_module_level=True)

from speasy.core.codecs import get_codec

AC_MFI = os.path.join(os.path.dirname(__file__), "resources", "ac_h2s_mfi_cdaweb.nc")


@pytest.fixture
def codec():
    c = get_codec("nc")
    assert c is not None
    return c


@pytest.fixture
def nc_path(tmp_path):
    """Minimal ISTP-compliant NetCDF file for codec tests."""
    path = tmp_path / "test_istp.nc"
    ds = netCDF4.Dataset(str(path), "w")

    ds.createDimension("time", 10)

    epoch = ds.createVariable("Epoch", "f8", ("time",))
    epoch.units = "seconds since 1970-01-01"
    epoch.VAR_TYPE = "support_data"
    epoch[:] = np.arange(10) * 60.0

    density = ds.createVariable("DENSITY", "f4", ("time",))
    density.VAR_TYPE = "data"
    density.DEPEND_0 = "Epoch"
    density.UNITS = "cm**-3"
    density[:] = np.linspace(1.0, 10.0, 10).astype("f4")

    ds.close()
    return str(path)


class TestNetCDFCodecResolution(unittest.TestCase):

    def test_codec_found_by_extension(self):
        self.assertIsNotNone(get_codec("nc"))

    def test_codec_found_by_extension_nc4(self):
        self.assertIsNotNone(get_codec("nc4"))


class TestNetCDFCodecRead:

    def test_load_variable_returns_result(self, codec, nc_path):
        result = codec.load_variables(["DENSITY"], file=nc_path)
        assert result is not None
        assert "DENSITY" in result
        assert result["DENSITY"] is not None

    def test_loaded_variable_has_correct_shape(self, codec, nc_path):
        var = codec.load_variable("DENSITY", file=nc_path)
        assert var.values.shape[0] == 10

    def test_loaded_variable_has_time_axis(self, codec, nc_path):
        var = codec.load_variable("DENSITY", file=nc_path)
        assert var.time.dtype == np.dtype("datetime64[ns]")


@pytest.mark.skipif(not os.path.exists(AC_MFI), reason="real CDAWeb file not present")
class TestNetCDFCodecWrite:

    @pytest.fixture
    def var(self, codec):
        return codec.load_variable("Magnitude", file=AC_MFI, disable_cache=True)

    def test_save_returns_memoryview(self, codec, var):
        assert isinstance(codec.save_variables([var]), memoryview)

    def test_roundtrip_variable_is_loaded(self, codec, var):
        buf = codec.save_variables([var])
        assert codec.load_variable("Magnitude", file=bytes(buf), disable_cache=True) is not None

    def test_roundtrip_values(self, codec, var):
        buf = codec.save_variables([var])
        var2 = codec.load_variable("Magnitude", file=bytes(buf), disable_cache=True)
        np.testing.assert_array_almost_equal(var.values, var2.values)

    def test_roundtrip_time(self, codec, var):
        buf = codec.save_variables([var])
        var2 = codec.load_variable("Magnitude", file=bytes(buf), disable_cache=True)
        np.testing.assert_array_equal(var.time, var2.time)


@pytest.mark.skipif(not os.path.exists(AC_MFI), reason="real CDAWeb file not present")
class TestNetCDFCodecRealFile:

    def test_load_variable_returns_result(self, codec):
        result = codec.load_variables(["Magnitude"], file=AC_MFI)
        assert result is not None
        assert result["Magnitude"] is not None

    def test_loaded_variable_has_correct_shape(self, codec):
        var = codec.load_variable("Magnitude", file=AC_MFI)
        assert var.values.shape[0] == var.time.shape[0]

    def test_loaded_variable_has_time_axis(self, codec):
        var = codec.load_variable("Magnitude", file=AC_MFI)
        assert var.time.dtype == np.dtype("datetime64[ns]")
