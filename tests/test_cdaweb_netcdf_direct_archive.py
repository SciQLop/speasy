#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""CDAWeb's 70 NetCDF datasets, served by direct file access when the codec can read them.

See https://github.com/SciQLop/speasy/issues/332: the container format says nothing about whether
the ISTP codec can read a file, so eligibility is settled by probing one real file. No CDAWeb
NetCDF dataset passes that probe today -- 65 of the 70 expose none but VIRTUAL parameters, four
are described with a sample file name instead of a pattern, and the last one makes pyistp raise --
so what these tests mostly pin down is that each of those cases falls back to the REST API.
"""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ddt import data, ddt

from speasy.core.codecs import get_codec
from speasy.data_providers.cda import _archive_params_for, _codec_can_read
from speasy.data_providers.cda._direct_archive import to_direct_archive_params

try:
    import netCDF4
except ImportError:
    netCDF4 = None

ICON = ('icon_l2-1_mighti-a_los-wind-green_%Y%m%d_v06r000.nc', '%Y',
        'https://cdaweb.gsfc.nasa.gov/pub/data/icon/l2/l2-1_mighti-a_los-wind-green')


@ddt
class TestFileFormatSelectsCodec(unittest.TestCase):

    def test_netcdf_datasets_are_read_with_the_netcdf_codec(self):
        file_naming, subdivided_by, url = ICON
        params = to_direct_archive_params(file_naming=file_naming, subdivided_by=subdivided_by, url=url)
        self.assertEqual(params['codec'], 'nc')

    def test_cdf_datasets_keep_the_default_reader(self):
        params = to_direct_archive_params(file_naming='mms1_fgm_srvy_l2_%Y%m%d_%Q.cdf', subdivided_by='%Y/%m',
                                          url='https://cdaweb.gsfc.nasa.gov/pub/data/mms/mms1/fgm/srvy/l2')
        self.assertNotIn('codec', params)

    @data('timed_L1Cdisk_guvi_1216A_SP_Movies_%Y%m%d%H%M%S_%Q.gif', 'po_h0_uvi_%Y%m%d_%Q.mpg')
    def test_formats_speasy_cannot_read_have_no_archive_params(self, file_naming):
        self.assertIsNone(to_direct_archive_params(file_naming=file_naming, subdivided_by='%Y',
                                                   url='https://cdaweb.gsfc.nasa.gov/pub/data/somewhere'))


def _regular_parameter():
    return SimpleNamespace()


def _cdaweb_dataset(url: str, file_naming: str = 'probe_%Y%m%d_v01.nc', subdivided_by: str = 'None',
                    master_cdf: str = 'https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/probe.cdf'):
    return SimpleNamespace(filenaming=file_naming, subdividedby=subdivided_by, url=url, mastercdf=master_cdf)


class TestCdfDatasetsAreServedWithoutProbing(unittest.TestCase):

    def test_cdf_datasets_are_given_their_master(self):
        params = _archive_params_for(_cdaweb_dataset(url='https://cdaweb.gsfc.nasa.gov/pub/data/probe',
                                                     file_naming='probe_%Y%m%d_%Q.cdf'),
                                     _regular_parameter(), 'DENSITY', '2020-01-02', '2020-01-03')
        self.assertEqual(params['master_cdf_url'],
                         'https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/probe.cdf')

    def test_virtual_parameters_are_never_served_from_files(self):
        self.assertIsNone(_archive_params_for(_cdaweb_dataset(url='https://cdaweb.gsfc.nasa.gov/pub/data/probe',
                                                              file_naming='probe_%Y%m%d_%Q.cdf'),
                                              SimpleNamespace(VIRTUAL='TRUE'), 'DENSITY',
                                              '2020-01-02', '2020-01-03'))


class TestUnavailableCodecFallsBackToTheWebService(unittest.TestCase):

    def test_dataset_whose_codec_is_not_installed_is_not_served_from_files(self):
        # netCDF4 has no WASM/Pyodide wheel, so the NetCDF codec isn't registered there at all and
        # get_codec('nc') answers None
        with tempfile.TemporaryDirectory() as archive:
            open(os.path.join(archive, 'probe_20200102_v01.nc'), 'w').close()
            with patch('speasy.data_providers.cda.get_codec', return_value=None):
                self.assertIsNone(_archive_params_for(_cdaweb_dataset(url=archive), _regular_parameter(),
                                                      'DENSITY', '2020-01-02', '2020-01-03'))


def _write_netcdf(path: str, istp: bool):
    """One tiny NetCDF file, with or without the DEPEND_0/VAR_TYPE attributes pyistp needs."""
    ds = netCDF4.Dataset(path, 'w')
    ds.createDimension('time', 3)
    epoch = ds.createVariable('Epoch', 'f8', ('time',))
    epoch.units = 'seconds since 1970-01-01'
    epoch[:] = [0., 60., 120.]
    density = ds.createVariable('DENSITY', 'f4', ('time',))
    density[:] = [1., 2., 3.]
    if istp:
        epoch.VAR_TYPE = 'support_data'
        density.VAR_TYPE = 'data'
        density.DEPEND_0 = 'Epoch'
    ds.close()


@unittest.skipIf(netCDF4 is None, "netCDF4 not installed")
class TestNetCDFDatasetsAreProbedBeforeServingFiles(unittest.TestCase):

    def _params_for(self, archive_holds: str, start_time: str, stop_time: str, istp: bool = True,
                    file_naming: str = 'probe_%Y%m%d_v01.nc', variable: str = 'DENSITY'):
        with tempfile.TemporaryDirectory() as archive:
            _write_netcdf(os.path.join(archive, archive_holds), istp=istp)
            return _archive_params_for(_cdaweb_dataset(url=archive, file_naming=file_naming),
                                       _regular_parameter(), variable, start_time, stop_time)

    def test_istp_conformant_dataset_is_served_from_files(self):
        params = self._params_for('probe_20200102_v01.nc', '2020-01-02', '2020-01-03')
        self.assertEqual(params['codec'], 'nc')

    def test_netcdf_datasets_are_not_given_a_master_cdf(self):
        # IstpNetCDF.load_variable forwards unknown kwargs down to _load_variables(variables, file,
        # buffer), which would raise TypeError on master_cdf_url
        params = self._params_for('probe_20200102_v01.nc', '2020-01-02', '2020-01-03')
        self.assertNotIn('master_cdf_url', params)

    def test_dataset_the_codec_reads_nothing_from_falls_back_to_the_web_service(self):
        # plain NetCDF, no ISTP attributes: direct access would yield an empty dataset, which is
        # strictly worse than the REST API answer it replaces
        self.assertIsNone(self._params_for('probe_20200102_v01.nc', '2020-01-02', '2020-01-03', istp=False))

    def test_dataset_with_no_file_in_the_requested_range_falls_back_to_the_web_service(self):
        # nothing to probe means nothing proven
        self.assertIsNone(self._params_for('probe_20200102_v01.nc', '2019-06-01', '2019-06-02'))

    def test_variable_missing_from_the_files_falls_back_to_the_web_service(self):
        # the file lists variables, just not the one asked for
        self.assertIsNone(self._params_for('probe_20200102_v01.nc', '2020-01-02', '2020-01-03',
                                           variable='SOMETHING_ELSE'))

    def test_variable_the_codec_chokes_on_falls_back_to_the_web_service(self):
        # listing a variable doesn't mean the codec can load it: on the real
        # ICON_L2-7_IVM-A files pyistp lists 125 variables and then raises
        # "AttributeError: NetCDF: Attribute not found" while walking ICON_L27_GPS_Epoch's axes
        with patch.object(get_codec('nc'), 'load_variable', side_effect=AttributeError("NetCDF: Attribute not found")):
            self.assertIsNone(self._params_for('probe_20200102_v01.nc', '2020-01-02', '2020-01-03'))

    def test_single_file_dataset_is_probed_through_the_folder_listing(self):
        # a dataset held in one fixed file is a regular split, which resolves its file differently
        params = self._params_for('the_whole_mission.nc', '2018-10-05', '2018-10-06',
                                  file_naming='the_whole_mission.nc')
        self.assertEqual(params['codec'], 'nc')

    def test_single_file_dataset_whose_file_is_missing_falls_back_to_the_web_service(self):
        self.assertIsNone(self._params_for('something_else.nc', '2018-10-05', '2018-10-06',
                                           file_naming='the_whole_mission.nc'))


@unittest.skipIf(netCDF4 is None, "netCDF4 not installed")
class TestProbeVerdictsAreRemembered(unittest.TestCase):
    """Probing downloads and decodes a real file, so the answer is kept for a week -- but only
    when it is an answer about the dataset. A file that could not be reached says nothing about
    it, and remembering that for a week would keep a perfectly readable dataset on the REST API
    long after the outage ended.
    """

    def setUp(self):
        _codec_can_read.drop_entries()

    def tearDown(self):
        _codec_can_read.drop_entries()

    def test_a_readable_file_is_not_decoded_twice(self):
        with patch.object(get_codec('nc'), 'load_variable', return_value=object()) as load_variable:
            self.assertTrue(_codec_can_read('file:///probe_readable.nc', 'nc', 'DENSITY'))
            self.assertTrue(_codec_can_read('file:///probe_readable.nc', 'nc', 'DENSITY'))
        self.assertEqual(load_variable.call_count, 1)

    def test_a_file_the_codec_chokes_on_is_not_decoded_twice(self):
        with patch.object(get_codec('nc'), 'load_variable',
                          side_effect=AttributeError("NetCDF: Attribute not found")):
            self.assertFalse(_codec_can_read('file:///probe_broken.nc', 'nc', 'DENSITY'))
        with patch.object(get_codec('nc'), 'load_variable', return_value=object()) as load_variable:
            self.assertFalse(_codec_can_read('file:///probe_broken.nc', 'nc', 'DENSITY'))
            load_variable.assert_not_called()

    def test_an_unreachable_file_is_not_remembered_as_a_verdict(self):
        with patch.object(get_codec('nc'), 'load_variable', side_effect=IOError("connection reset")):
            with self.assertRaises(IOError):
                _codec_can_read('file:///probe_unreachable.nc', 'nc', 'DENSITY')
        with patch.object(get_codec('nc'), 'load_variable', return_value=object()) as load_variable:
            self.assertTrue(_codec_can_read('file:///probe_unreachable.nc', 'nc', 'DENSITY'))
            load_variable.assert_called_once()

    def test_each_variable_of_a_file_gets_its_own_verdict(self):
        with patch.object(get_codec('nc'), 'load_variable', return_value=object()) as load_variable:
            _codec_can_read('file:///probe_per_variable.nc', 'nc', 'DENSITY')
            _codec_can_read('file:///probe_per_variable.nc', 'nc', 'TEMPERATURE')
        self.assertEqual(load_variable.call_count, 2)


if __name__ == '__main__':
    unittest.main()
