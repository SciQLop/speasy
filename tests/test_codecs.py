#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.core.codecs` package."""
import unittest

from ddt import ddt, data, unpack

import os
import tempfile
from unittest import mock
import numpy as np
from speasy.core.codecs import get_codec

__HERE__ = os.path.dirname(os.path.abspath(__file__))


@ddt
class TestCodecResolution(unittest.TestCase):

    @data("cdf", "application/x-cdf")
    def test_codec_resolution(self, codec):
        self.assertIsNotNone(get_codec(codec))

    def test_unknown_codec_raises_listing_registered_ones(self):
        with self.assertRaisesRegex(ValueError, r"Unknown codec 'csv'.*'cdf'.*'hapi/csv'"):
            get_codec('csv')

    @data(("unknown", False), ("cdf", True))
    @unpack
    def test_has_codec(self, codec, expected):
        from speasy.core.codecs import has_codec
        self.assertEqual(has_codec(codec), expected)


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
        (f"{__HERE__}/resources/HAPI_sample_csv.csv", "hapi/csv", ['Magnitude']),
        ("https://hapi-server.org/servers/TestData2.0/hapi/data?id=dataset1&parameters=scalar,vector&time.min=1970-01-01T00:00:00Z&time.max=1970-01-01T00:01:00Z&include=header", "hapi/csv", ['scalar', 'vector']),
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
        source_file = f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf"

        original = codec.load_variable("BGSEc", source_file, disable_cache=True)
        buffer = codec.save_variables([original])
        cls.v = codec.load_variable("BGSEc", buffer, disable_cache=True)

    def test_variable_is_loaded(self):
        self.assertIsNotNone(self.v)

    def test_variable_shape(self):
        self.assertEqual(self.v.values.shape, (24, 3))


class TestCDFWriterPreservesAxisAttributes(unittest.TestCase):
    """`_write_axis` used to call `cdf.add_variable` with no `attributes=` at all, so an axis's
    own metadata (SCALETYP, UNITS, ...) never made it into the file, even though the primary
    variable's metadata did."""

    @classmethod
    def setUpClass(cls):
        from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
        from speasy.products import SpeasyVariable

        time = np.arange('2018-01-01', '2018-01-01T00:01', np.timedelta64(10, 's'), dtype='datetime64[ns]')
        energy = VariableAxis(name='energy', values=np.arange(5).astype(np.float64),
                              meta={"SCALETYP": "log", "UNITS": "eV"})
        var = SpeasyVariable(
            axes=[VariableTimeAxis(values=time, meta={"UNITS": "ns"}), energy],
            values=DataContainer(np.random.random((len(time), 5)), is_time_dependent=True, name='flux',
                                 meta={"VAR_TYPE": "data"}),
            columns=["Values"])

        codec = get_codec("application/x-cdf")
        buffer = codec.save_variables([var])
        cls.back = codec.load_variable('flux', file=bytes(buffer), disable_cache=True)

    def test_non_time_axis_meta_survives(self):
        self.assertEqual(self.back.axes[1].meta.get("SCALETYP"), "log")
        self.assertEqual(self.back.axes[1].meta.get("UNITS"), "eV")

    def test_time_axis_meta_survives(self):
        self.assertEqual(self.back.axes[0].meta.get("UNITS"), "ns")


def _vector(name="test", meta=None, columns=("c0", "c1", "c2"), start="2020-01-01"):
    from speasy.core.data_containers import DataContainer, VariableTimeAxis
    from speasy.products import SpeasyVariable
    time = np.datetime64(start, 'ns') + np.arange(4) * np.timedelta64(1, 's')
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                          values=DataContainer(np.random.random((4, len(columns))), name=name, is_time_dependent=True,
                                               meta=dict(meta if meta is not None else {"UNITS": "nT", "VAR_TYPE": "data"})),
                          columns=list(columns))


@ddt
class TestWritersLeaveTheSourceUntouched(unittest.TestCase):

    @data("cdf", "nc", "hapi/csv", "hapi/binary")
    def test_meta_is_not_mutated(self, codec_id):
        v = _vector()
        before = dict(v.meta)
        get_codec(codec_id).save_variables([v])
        self.assertEqual(before, v.meta)


@ddt
class TestSavingSeveralVariables(unittest.TestCase):

    @data("cdf", "nc")
    def test_time_axes_sharing_a_name_but_not_values_are_kept_apart(self, codec_id):
        b, n = _vector(name="b"), _vector(name="n", start="2021-06-01", columns=("x", "y"))
        codec = get_codec(codec_id)
        loaded = codec.load_variables(["b", "n"], bytes(codec.save_variables([b, n])))
        np.testing.assert_array_equal(b.time, loaded["b"].time)
        np.testing.assert_array_equal(n.time, loaded["n"].time)
        np.testing.assert_array_equal(n.values, loaded["n"].values)

    def test_identical_time_axes_are_written_once(self):
        b = _vector(name="b")
        n = _vector(name="n")
        import pycdfpp
        cdf = pycdfpp.load(bytes(get_codec("cdf").save_variables([b, n])))
        time_variables = [name for name in cdf if cdf[name].type == pycdfpp.DataType.CDF_TIME_TT2000]
        self.assertEqual(["time"], time_variables)


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


class TestListVariables(unittest.TestCase):

    def test_list_variables_cdf(self):
        codec = get_codec("cdf")
        variables = codec.list_variables(f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf")
        self.assertIn('Magnitude', variables)
        self.assertIn('BGSEc', variables)

    def test_list_variables_netcdf(self):
        codec = get_codec("nc")
        variables = codec.list_variables(f"{__HERE__}/resources/ac_h2s_mfi_cdaweb.nc")
        self.assertIn('Magnitude', variables)
        self.assertIn('BGSEc', variables)

    def test_list_variables_raises_when_codec_does_not_implement_it(self):
        # Neither HapiCsv nor its base class HapiBaseCodec overrides list_variables, so both
        # inherit CodecInterface's own default implementation, which explicitly raises
        # NotImplementedError -- a codec that cannot list the variables of a file must say so
        # rather than silently fail some other way. The file is never read, it only has to exist.
        codec = get_codec("hapi/csv")
        self.assertIsNotNone(codec)
        with self.assertRaises(NotImplementedError):
            codec.list_variables(f"{__HERE__}/resources/ac_k2_mfi_20220101_v03.cdf")


from speasy.core.codecs import get_codec, CodecInterface
from speasy.core.codecs import codecs_registry
from speasy.core import plugins
from speasy.products import DataContainer, SpeasyVariable, VariableTimeAxis


class _TinyCodec(CodecInterface):
    """Minimal codec used to prove registration paths; mirrors the test codec in
    test_direct_archive_inventory.py."""

    def list_variables(self, file):
        return ['foo']

    def load_variables(self, variables, file, cache_remote_files=True, **kwargs):
        time = np.array(['2020-01-01'], dtype='datetime64[ns]')
        var = SpeasyVariable(axes=[VariableTimeAxis(values=time)],
                             values=DataContainer(values=np.array([1.0])))
        return {v: var for v in variables}

    def load_variable(self, variable, file, cache_remote_files=True, **kwargs):
        return self.load_variables([variable], file, cache_remote_files, **kwargs).get(variable)

    def save_variables(self, variables, file=None, **kwargs):
        raise NotImplementedError

    @property
    def supported_extensions(self):
        return ['tiny']

    @property
    def supported_mimetypes(self):
        return []

    @property
    def name(self):
        return 'codec/tiny-entry-point'


class EntryPointCodecs(unittest.TestCase):

    def _load_through_entry_point(self, register):
        ep = mock.MagicMock()
        ep.name = 'tiny'
        ep.value = 'tiny_pkg:register'
        ep.load.return_value = register
        with mock.patch.object(plugins, 'entry_points', return_value=[ep]):
            plugins.load_plugins('speasy.codecs')

    def test_a_codec_shipped_through_an_entry_point_is_registered(self):
        from speasy.core.codecs import register_codec
        self._load_through_entry_point(lambda: register_codec(_TinyCodec))
        try:
            self.assertIsNotNone(get_codec('codec/tiny-entry-point'))
            self.assertIsNotNone(get_codec('tiny'))
        finally:
            codecs_registry.__CODECS__.pop('codec/tiny-entry-point', None)
            codecs_registry.__CODECS__.pop('tiny', None)

    def test_a_codec_colliding_with_a_bundled_one_is_refused_and_reported(self):
        from speasy.core.codecs import register_codec

        class _Impostor(_TinyCodec):
            @property
            def supported_extensions(self):
                return ['cdf']   # bundled ISTP codec already owns cdf

            @property
            def name(self):
                return 'codec/impostor'

        bundled = get_codec('cdf')
        with self.assertLogs('speasy.core.plugins', level='WARNING'):
            self._load_through_entry_point(lambda: register_codec(_Impostor))
        codecs_registry.__CODECS__.pop('codec/impostor', None)  # name lands before the ext collision
        self.assertIs(get_codec('cdf'), bundled)


class UserDirectoryCodecFailuresAreContained(unittest.TestCase):

    _VALID_CODEC_FILE = '''\
from speasy.core.codecs.codec_interface import CodecInterface
from speasy.core.codecs.codecs_registry import register_codec


@register_codec
class _UserDirValidCodec(CodecInterface):

    def load_variables(self, variables, file, cache_remote_files=True, **kwargs):
        raise NotImplementedError

    def load_variable(self, variable, file, cache_remote_files=True, **kwargs):
        raise NotImplementedError

    def save_variables(self, variables, file=None, **kwargs):
        raise NotImplementedError

    @property
    def supported_extensions(self):
        return ['udv']

    @property
    def supported_mimetypes(self):
        return []

    @property
    def name(self):
        return 'codec/user-dir-valid'
'''

    def test_a_broken_codec_file_is_skipped_and_the_valid_one_still_loads(self):
        with tempfile.TemporaryDirectory() as codec_dir:
            with open(os.path.join(codec_dir, 'broken.py'), 'w') as f:
                f.write("raise RuntimeError('this codec file is broken')\n")
            with open(os.path.join(codec_dir, 'valid.py'), 'w') as f:
                f.write(self._VALID_CODEC_FILE)
            try:
                with mock.patch.object(codecs_registry, 'user_codecs_dir',
                                       return_value='/nonexistent-speasy-user-codecs-dir'):
                    with mock.patch.object(codecs_registry.cfg.user_codecs_extra_dirs, 'get',
                                           return_value={codec_dir}):
                        with self.assertLogs('speasy.core.codecs.codecs_registry', level='WARNING') as captured:
                            codecs_registry.load_extra_codecs()
                self.assertTrue(any('broken.py' in line for line in captured.output))
                self.assertIsNotNone(get_codec('codec/user-dir-valid'))
            finally:
                codecs_registry.__CODECS__.pop('codec/user-dir-valid', None)
                codecs_registry.__CODECS__.pop('udv', None)
