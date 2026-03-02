import os
import unittest

import numpy as np
from ddt import data, ddt, unpack

from speasy.core.codecs import CodecInterface, get_codec
from speasy.core.codecs.bundled_codecs.hapi_csv.codec import _bin_to_axis, _bins_to_axes
from speasy.core.codecs.bundled_codecs.hapi_csv.reader import load_hapi_csv
from speasy.core.data_containers import VariableAxis
from speasy.products import SpeasyVariable

__HERE__ = os.path.dirname(__file__)


@ddt
class TestHapiCsvCodec(unittest.TestCase):

    @data(
        ('HAPI_sample_csv.csv', 'Magnitude', 'nT', "B-field magnitude"),
        ('HAPI_sample_csv_multiple_vars.csv', 'Magnitude', 'nT', "B-field magnitude"),
        ('HAPI_sample_csv_multiple_vars.csv', 'BGSEc', 'nT',
         'Magnetic Field Vector in GSE Cartesian coordinates (1 hr)'),
        ('HAPI_sample_csv_multiple_vars.csv', 'BGSM', 'nT', 'Magnetic field vector in GSM coordinates (1 hr)'),
        ('HAPI_sample_csv_multiple_vars.csv', 'SC_pos_GSE', 'km', 'ACE s/c position, 3 comp. in GSE coord.')
    )
    @unpack
    def test_loads_headers(self, fname, var_name, unit, description):
        hapi_csv_codec: CodecInterface = get_codec('hapi/csv')
        with open(os.path.join(__HERE__, 'resources', fname), 'r') as f:
            v: SpeasyVariable = hapi_csv_codec.load_variable(file=f, variable=var_name, disable_cache=True)
            self.assertEqual(v.unit, unit)
            self.assertEqual(v.meta['description'], description)

    @data(
        ('HAPI_sample_csv.csv', 'Magnitude', np.datetime64("1997-09-02T00:00:00.000Z"), np.datetime64("1997-09-03T23:00:00.000Z")),
        ('HAPI_sample_csv_multiple_vars.csv', 'Magnitude', np.datetime64("1997-09-02T00:00:00.000Z"), np.datetime64("1997-09-03T23:00:00.000Z"))
    )
    @unpack
    def test_load_time_index(self, fname, var_name, first_value, last_value):
        hapi_csv_codec: CodecInterface = get_codec('hapi/csv')
        v: SpeasyVariable = hapi_csv_codec.load_variable(
            file=str(os.path.join(__HERE__, 'resources', 'HAPI_sample_csv_multiple_vars.csv')), variable=var_name,
            disable_cache=True)
        self.assertEqual(v.time[0], first_value)
        self.assertEqual(v.time[-1], last_value)

    @data(
        ('HAPI_sample_csv.csv', 'Magnitude', (48, 1), 2.658, 14.743),
        ('HAPI_sample_csv_multiple_vars.csv', 'Magnitude', (48, 1), 2.658, 14.743),
        ('HAPI_sample_csv_multiple_vars.csv', 'BGSEc', (48, 3), [0.654, -1.157, -2.252], [4.955, -5.523, 3.774]),
        ('HAPI_sample_csv_multiple_vars.csv', 'BGSM', (48, 3), [6.540e-01, -1.622e+00, -1.944e+00],
         [4.955e+00, -4.626e+00, 4.835e+00]),
        ('HAPI_sample_csv_multiple_vars.csv', 'SC_pos_GSE', (48, 3), [744944.0, 37435.0, 95794.0],
         [842254.0, 30870.0, 103923.0])
    )
    @unpack
    def test_load_values(self, fname, var_name, shape, first_value, last_value):
        hapi_csv_codec: CodecInterface = get_codec('hapi/csv')
        v: SpeasyVariable = hapi_csv_codec.load_variable(
            file=str(os.path.join(__HERE__, 'resources', 'HAPI_sample_csv_multiple_vars.csv')), variable=var_name,
            disable_cache=True)
        self.assertEqual(v.values.shape, shape)
        if type(first_value) is list:
            self.assertListEqual(v.values[0].tolist(), first_value)
            self.assertListEqual(v.values[-1].tolist(), last_value)
        else:
            self.assertEqual(v.values[0], first_value)
            self.assertEqual(v.values[-1], last_value)

    def test_load_multiple_variables(self):
        hapi_csv_codec: CodecInterface = get_codec('hapi/csv')
        with open(os.path.join(__HERE__, 'resources', 'HAPI_sample_csv_multiple_vars.csv'), 'r') as f:
            names = ['Magnitude', 'BGSEc', 'BGSM', 'SC_pos_GSE']
            variables = hapi_csv_codec.load_variables(file=f, variables=names, disable_cache=True)
            self.assertEqual(len(variables), len(names))
            for v in variables.values():
                self.assertEqual(v.values.shape[0], 48)
            self.assertListEqual(list(variables.keys()), names)
            self.assertEqual(variables['Magnitude'].unit, 'nT')
            self.assertEqual(variables['Magnitude'].meta['description'], 'B-field magnitude')
            self.assertEqual(variables['SC_pos_GSE'].unit, 'km')
            self.assertEqual(variables['SC_pos_GSE'].meta['description'], 'ACE s/c position, 3 comp. in GSE coord.')

    @data(
        ('HAPI_ndData_TimeVarying_Axis.csv', { "centers": "frequency_centers_time_varying" }),
        ('HAPI_ndData_TimeVarying_Axis.csv', {"centers": [0.1, 0.2, 0.3]})
    )
    @unpack
    def test_bin_to_axis(self, csv_file, json_bin):
        with open(os.path.join(__HERE__, 'resources', csv_file), 'r') as f:
            hapi_csv_file = load_hapi_csv(f)
            axis = _bin_to_axis(json_bin, hapi_csv_file)
            self.assertIsInstance(axis, VariableAxis)

    @data(
        ('HAPI_ndData_TimeVarying_Axis.csv',[
            { "centers": "frequency_centers_time_varying" },
            {"centers": [0.1, 0.2, 0.3]}])
    )
    @unpack
    def test_bins_to_axes(self, csv_file, json_bins):
        with open(os.path.join(__HERE__, 'resources', csv_file), 'r') as f:
            hapi_csv_file = load_hapi_csv(f)
            axes = _bins_to_axes(json_bins, hapi_csv_file)
            self.assertEqual(len(axes), len(json_bins))
            for axis in axes:
                self.assertIsInstance(axis, VariableAxis)

    def test_load_multi_axis_variable(self):
        hapi_csv_codec: CodecInterface = get_codec('hapi/csv')
        with open(os.path.join(__HERE__, 'resources', 'HAPI_ndData_TimeVarying_Axis.csv'), 'r') as f:
            variables = hapi_csv_codec.load_variables(file=f, variables=['spectra_time_dependent_bins'], disable_cache=True)
            self.assertIn('spectra_time_dependent_bins', variables)
