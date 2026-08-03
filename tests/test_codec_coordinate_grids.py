#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Codecs round-tripping variables whose axes give a coordinate per data cell.

Two shapes reach the writers: CDAWeb map products such as GOLD_L2_ON2, whose latitude and
longitude grids span the non-time dimensions, and PSP_ISOIS-EPILO_L2-PE, whose energy grid spans
every dimension including time. Both used to be written against a single dimension sized from one
of their own, which either raised or lost the record-varying flag on the way back.
"""

import unittest

import numpy as np
from ddt import data, ddt, unpack

from speasy.core.codecs import get_codec
from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products import SpeasyVariable

try:
    import netCDF4
except ImportError:
    netCDF4 = None

_TIME = np.arange('2018-10-05', '2018-10-05T00:01', np.timedelta64(10, 's'), dtype='datetime64[ns]')
_N, _H, _D = len(_TIME), 5, 3


def coordinate_grids() -> SpeasyVariable:
    """GOLD_L2_ON2's shape: latitude and longitude grids over the two spatial dimensions."""
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=_TIME),
              VariableAxis(name='latitude', values=np.random.random((_H, _D))),
              VariableAxis(name='longitude', values=np.random.random((_H, _D)))],
        values=DataContainer(np.random.random((_N, _H, _D)), is_time_dependent=True, name='on2',
                             meta={"VAR_TYPE": "data", "DISPLAY_TYPE": "map_image"}),
        columns=["Values"])


def record_varying_grid() -> SpeasyVariable:
    """PSP_ISOIS-EPILO_L2-PE's shape: an energy grid given for every (time, look direction) cell."""
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=_TIME),
              VariableAxis(name='look_direction', values=np.arange(_H).astype(np.float64)),
              VariableAxis(name='energy', values=np.random.random((_N, _H, _D)), is_time_dependent=True)],
        values=DataContainer(np.random.random((_N, _H, _D)), is_time_dependent=True, name='counts',
                             meta={"VAR_TYPE": "data", "DISPLAY_TYPE": "spectrogram"}),
        columns=["Values"])


def plain_spectrogram() -> SpeasyVariable:
    """One value per index, the shape that already worked, kept so the fix stays a superset."""
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=_TIME),
              VariableAxis(name='energy', values=np.arange(_H).astype(np.float64))],
        values=DataContainer(np.random.random((_N, _H)), is_time_dependent=True, name='flux',
                             meta={"VAR_TYPE": "data", "DISPLAY_TYPE": "spectrogram"}),
        columns=["Values"])


def _round_trip(codec_name: str, var: SpeasyVariable) -> SpeasyVariable:
    buffer = get_codec(codec_name).save_variables([var])
    return get_codec(codec_name).load_variable(var.name, file=bytes(buffer), disable_cache=True)


@ddt
class CoordinateGridsSurviveACdfRoundTrip(unittest.TestCase):

    @data(coordinate_grids, record_varying_grid, plain_spectrogram)
    def test_shapes_are_preserved(self, ctor):
        var = ctor()
        back = _round_trip('cdf', var)
        self.assertIsNotNone(back)
        self.assertEqual(back.values.shape, var.values.shape)
        self.assertListEqual([ax.shape for ax in back.axes], [ax.shape for ax in var.axes])

    @data(coordinate_grids, record_varying_grid, plain_spectrogram)
    def test_time_dependence_is_preserved(self, ctor):
        # a record-varying axis written without DEPEND_0 comes back time independent, and then
        # matches no dimension of the data at all
        var = ctor()
        back = _round_trip('cdf', var)
        self.assertListEqual([ax.is_time_dependent for ax in back.axes],
                             [ax.is_time_dependent for ax in var.axes])

    @data(coordinate_grids, record_varying_grid, plain_spectrogram)
    def test_values_are_preserved(self, ctor):
        var = ctor()
        back = _round_trip('cdf', var)
        np.testing.assert_array_almost_equal(back.values, var.values)


@unittest.skipIf(netCDF4 is None, "netCDF4 not installed")
@ddt
class CoordinateGridsSurviveANetCdfRoundTrip(unittest.TestCase):

    @data(coordinate_grids, record_varying_grid, plain_spectrogram)
    def test_shapes_are_preserved(self, ctor):
        var = ctor()
        back = _round_trip('nc', var)
        self.assertIsNotNone(back)
        self.assertEqual(back.values.shape, var.values.shape)
        self.assertListEqual([ax.shape for ax in back.axes], [ax.shape for ax in var.axes])

    @data(coordinate_grids, record_varying_grid, plain_spectrogram)
    def test_values_are_preserved(self, ctor):
        var = ctor()
        back = _round_trip('nc', var)
        np.testing.assert_array_almost_equal(back.values, var.values)

    @data((coordinate_grids, ('dim_latitude', 'dim_longitude'), (_H, _D)),
          (record_varying_grid, ('dim_look_direction', 'dim_energy'), (_H, _D)))
    @unpack
    def test_each_data_dimension_gets_its_own_size(self, ctor, dimension_names, sizes):
        # both grids used to size their dimension from their own first (or last) axis, so the two
        # spatial dimensions ended up sharing one size and nothing fitted
        buffer = get_codec('nc').save_variables([ctor()])
        with netCDF4.Dataset('probe', mode='r', memory=bytes(buffer)) as ds:
            self.assertEqual(tuple(len(ds.dimensions[name]) for name in dimension_names), sizes)


if __name__ == '__main__':
    unittest.main()
