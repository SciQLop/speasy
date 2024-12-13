#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.core.codecs` package."""
import unittest

from ddt import ddt, data, unpack

import os
from speasy.core.codecs import get_codec

__HERE__ = os.path.dirname(os.path.abspath(__file__))


@ddt
class TestCodecResolution(unittest.TestCase):

    @data(
        ("unknown", False),
        ("cdf", True),
        ("application/x-cdf", True),
    )
    @unpack
    def test_codec_resolution(self, codec, expected):
        self.assertEqual(get_codec(codec) is not None, expected)


@ddt
class TestReadFiles(unittest.TestCase):

    @data(
        (f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf", "cdf", ['Magnitude', 'BGSEc']),
        (
            "https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/mms/mms3/fpi/fast/l2/dis-moms/2022/07/mms3_fpi_fast_l2_dis-moms_20220701040000_v3.4.0.cdf",
            "application/x-cdf", ['mms3_dis_errorflags_fast',
                                  'mms3_dis_startdelphi_count_fast',
                                  'mms3_dis_startdelphi_angle_fast',
                                  'mms3_dis_energyspectr_px_fast',
                                  'mms3_dis_energyspectr_mx_fast',
                                  'mms3_dis_energyspectr_py_fast',
                                  'mms3_dis_energyspectr_my_fast',
                                  'mms3_dis_energyspectr_pz_fast',
                                  'mms3_dis_energyspectr_mz_fast',
                                  'mms3_dis_energyspectr_omni_fast',
                                  'mms3_dis_spectr_bg_fast',
                                  'mms3_dis_numberdensity_bg_fast',
                                  'mms3_dis_numberdensity_fast',
                                  'mms3_dis_densityextrapolation_low_fast',
                                  'mms3_dis_densityextrapolation_high_fast',
                                  'mms3_dis_bulkv_dbcs_fast',
                                  'mms3_dis_bulkv_spintone_dbcs_fast',
                                  'mms3_dis_bulkv_gse_fast',
                                  'mms3_dis_bulkv_spintone_gse_fast',
                                  'mms3_dis_prestensor_dbcs_fast',
                                  'mms3_dis_prestensor_gse_fast',
                                  'mms3_dis_pres_bg_fast',
                                  'mms3_dis_temptensor_dbcs_fast',
                                  'mms3_dis_temptensor_gse_fast',
                                  'mms3_dis_heatq_dbcs_fast',
                                  'mms3_dis_heatq_gse_fast',
                                  'mms3_dis_temppara_fast',
                                  'mms3_dis_tempperp_fast']),
    )
    @unpack
    def test_read_files(self, filename, codec_id, variables):
        codec = get_codec(codec_id)
        self.assertIsNotNone(codec)
        data = codec.load_variables(variables, file=filename)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), len(variables))
        for variable in variables:
            self.assertIsNotNone(data[variable])
            self.assertIsNotNone(data[variable].values)


class TestCDFWriter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        codec = get_codec("application/x-cdf")
        cls.v = codec.load_variable("BGSEc", codec.save_variables(
            [codec.load_variable("BGSEc", f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf")]))

    def test_variable_is_loaded(self):
        self.assertIsNotNone(self.v)

    def test_variable_shape(self):
        self.assertEqual(self.v.values.shape, (24, 3))


@ddt
class TestCDFWriterPtrAttributes(unittest.TestCase):

    @data(
        (f"{__HERE__}/resources/ge_h0_cpi_00000000_v01.cdf", "cdf", "SW_V"),
    )
    @unpack
    def test_read_files(self, filename, codec_id, variable):
        codec = get_codec(codec_id)
        self.assertIsNotNone(codec)
        data = codec.load_variable(variable, file=filename)
        buffer = codec.save_variables([data])
        self.assertIsNotNone(buffer)
