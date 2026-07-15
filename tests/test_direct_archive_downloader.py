import os
import unittest
from multiprocessing import Pool
from ddt import ddt, data, unpack
import numpy as np

import speasy as spz
from speasy.core import make_utc_datetime
from speasy.core.cdf.inventory_extractor import extract_parameters
from speasy.core.direct_archive_downloader import get_product
import speasy.core.direct_archive_downloader.direct_archive_downloader as dad

__HERE__ = os.path.dirname(os.path.abspath(__file__))


def _custom_cdf_loader(url, variable, *args, **kwargs):
    v = dad._read_cdf(url, variable, *args, **kwargs)
    v.meta["_custom_cdf_loader"] = True
    return v


@ddt
class DirectArchiveDownloader(unittest.TestCase):
    def setUp(self):
        pass

    def test_split_rules(self):
        self.assertListEqual(dad.spilt_range(split_frequency='daily', start_time='2010-01-01', stop_time='2010-01-01'),
                             [make_utc_datetime('2010-01-01')]
                             )
        self.assertListEqual(dad.spilt_range(split_frequency='monthly', start_time='2010-01-01', stop_time='2010-01-01'),
                             [make_utc_datetime('2010-01-01')]
                             )
        self.assertListEqual(dad.spilt_range(split_frequency='yearly', start_time='2010-01-01', stop_time='2010-01-01'),
                             [make_utc_datetime('2010-01-01')]
                             )

        self.assertListEqual(dad.spilt_range(split_frequency='daily', start_time='2010-01-01', stop_time='2010-01-02'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-01-02')]
                             )
        self.assertListEqual(dad.spilt_range(split_frequency='monthly', start_time='2010-01-01', stop_time='2010-02-01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-02-01')]
                             )
        self.assertListEqual(dad.spilt_range(split_frequency='yearly', start_time='2010-01-01', stop_time='2011-01-01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2011-01-01')]
                             )

        self.assertListEqual(dad.spilt_range(split_frequency='daily', start_time='2010-01-01', stop_time='2010-01-02T01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-01-02')]
                             )
        self.assertListEqual(dad.spilt_range(split_frequency='monthly', start_time='2010-01-01', stop_time='2010-02-01T01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-02-01')]
                             )
        self.assertListEqual(dad.spilt_range(split_frequency='yearly', start_time='2010-01-01', stop_time='2011-01-01T01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2011-01-01')]
                             )

    def test_unknown_split_rules_raises(self):
        with self.assertRaises(ValueError):
            dad.spilt_range(split_frequency='unknown', start_time='2010-01-01', stop_time='2011-01-01')

    @data(
        (
                "https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3/1min/{Y}/erg_pwe_hfa_l3_1min_{Y}{M:02d}{D:02d}_v05_11.cdf",
                "regular", "ne_mgf", "2018-02-01", "2018-02-02"),
        (
                "http://themis.ssl.berkeley.edu/data/themis/thb/l2/scm/{Y}/thb_l2_scm_{Y}{M:02d}{D:02d}_v01.cdf",
                "regular", "thb_scf_gse", "2008-07-23T10", "2008-07-23T15"),
        (
                r"https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/rpw/low_latency/ll02/sbm1/{Y}/solo_ll02_rpw-sbm1_{Y}{M:02d}{D:02d}t\d+-\d+t\d+_v\d+u.cdf",
                "random", "DT1_SBM1", "2021-07-23T10", "2021-07-25T23",
                {'fname_regex': r'solo_ll02_rpw-sbm1_(?P<start>\d+t\d+)-(?P<stop>\d+t\d+)_v(?P<version>\d+)u\.cdf'}),
    )
    @unpack
    def test_download_existing_data(self, url_pattern, split_rule, variable, start_time, stop_time, kwargs=None):
        kwargs = kwargs or {}
        data = get_product(
            url_pattern=url_pattern,
            split_rule=split_rule,
            variable=variable, start_time=start_time, stop_time=stop_time, **kwargs)
        self.assertIsNotNone(data)

    @unittest.skip(
        "Segfaults (SIGSEGV): the netCDF4/HDF5 build is not thread-safe and speasy reads "
        "the .nc concurrently from its request thread pool; the corrupted HDF5 global state "
        "crashes a later netCDF4.Dataset open. See netcdf_thread_safety_segfault.md. "
        "Re-enable once the pyistp netcdf driver serializes access with a global lock."
    )
    def test_get_product_codec_override_reads_local_file(self):
        # get_product(codec=not_None) overrides the default codec with codec.load_variable.
        #
        #  the file_reader expects url-first arguments,
        #  but codec.load_variable expects variable-first arguments.
        #
        # This test fails before the fix in 2024-06-05,
        common = {"url_pattern": f"{__HERE__}/resources/ac_h2s_mfi_cdaweb.nc",
                  "split_rule": "regular", "variable": "Magnitude",
                  "start_time": "2009-06-01", "stop_time": "2009-06-03"}
        via_codec_file_loader = get_product(**common, codec="application/x-netcdf")
        self.assertIsNotNone(via_codec_file_loader)
        self.assertGreater(len(via_codec_file_loader), 0)

    def test_get_data_honors_declared_codec(self):
        # _get_data must forward the inventory 'codec' key to get_product,
        #
        # But a wrong pop of the codec key would cause default to be used.
        # This test fails before the fix
        from unittest.mock import patch
        from speasy.core.inventory.indexes import ParameterIndex
        from speasy.data_providers.generic_archive import GenericArchive

        nc = f"{__HERE__}/resources/ac_h2s_mfi_cdaweb.nc"
        cfg = {'inventory_path': 'archive/test/DS', 'master_cdf': nc,
               'url_pattern': nc, 'split_rule': 'regular',
               'codec': 'application/x-netcdf'}
        param = ParameterIndex(name='Magnitude', provider='archive',
                               uid='archive/test/DS/Magnitude',
                               meta={'spz_ga_cfg': dict(cfg)})
        provider = object.__new__(GenericArchive)
        with patch.object(dad, 'get_codec', wraps=dad.get_codec) as get_codec_spy:
            v = provider._get_data(product=param, start_time='2009-06-01', stop_time='2009-06-03')
        resolved = [c.args[0] for c in get_codec_spy.call_args_list if c.args]
        self.assertIsNotNone(v)
        self.assertGreater(len(v), 0)
        self.assertIn('application/x-netcdf', resolved)   # declared codec drove the read

    def test_get_data_does_not_mutate_inventory_config(self):
        # _get_data reads and pops product.spz_ga_cfg 
        # but this in place popping corrupts the inventory for later usages
        #
        # This test fails before the fix 
        from unittest.mock import patch
        from speasy.core.inventory.indexes import ParameterIndex
        from speasy.data_providers.generic_archive import GenericArchive

        cfg = {'inventory_path': 'archive/test/DS', 'master_cdf': 'https://x/master.cdf',
               'url_pattern': 'https://x/file.cdf', 'split_rule': 'regular'}
        param = ParameterIndex(name='X', provider='archive',
                               uid='archive/test/DS/X', meta={'spz_ga_cfg': cfg})
        provider = object.__new__(GenericArchive)
        with patch('speasy.data_providers.generic_archive.get_product', return_value=None):
            provider._get_data(product=param, start_time='2009-06-01', stop_time='2009-06-02')
        self.assertIn('inventory_path', param.spz_ga_cfg)   # must survive the previous _get_data call
        self.assertIn('master_cdf', param.spz_ga_cfg)

    def test_get_data_end_to_end_master_nc_values(self):
        # End-to-end through a NetCDF master: inventory build (ISTP path via
        # extract_from_master) + data retrieval, asserting values == native pyistp read.
        #
        # codec 'nc' plays a double role: it selects the ISTP build path in
        # _dataset_from_master AND resolves to the netcdf codec for get_product.
        import tempfile
        import yaml
        import pyistp
        from speasy.core.inventory.indexes import SpeasyIndex
        from speasy.data_providers.generic_archive import load_inventory_file, GenericArchive

        nc = f"{__HERE__}/resources/ac_h2s_mfi_cdaweb.nc"
        entry = {
            "DS_nc_master": {
                "inventory_path": "archive/test",
                "master_file": nc,
                "url_pattern": nc,
                "split_rule": "regular",
                "codec": "nc",
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(entry, f)
            yaml_path = f.name
        try:
            root = SpeasyIndex(name="root", provider="archive", uid="root")
            load_inventory_file(yaml_path, root)

            # Navigate the built tree to the Magnitude parameter (proves extract_from_master ran)
            dataset = root.archive.test.DS_nc_master
            param = dataset.Magnitude

            provider = object.__new__(GenericArchive)
            result = provider._get_data(product=param,
                                        start_time="2009-06-01", stop_time="2009-06-04")
        finally:
            os.unlink(yaml_path)

        oracle = pyistp.load(file=nc).data_variable("Magnitude").values

        self.assertIsNotNone(result)
        self.assertEqual(len(result), len(oracle))              # 49 points, nothing lost
        np.testing.assert_array_equal(result.values.ravel(), oracle.ravel())

    def test_get_product_with_custom_loader(self):
        v = get_product(
            url_pattern="https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3/1min/{Y}/erg_pwe_hfa_l3_1min_{Y}{M:02d}{D:02d}_v05_11.cdf",
            split_rule="regular",
            variable="ne_mgf", start_time="2018-02-01", stop_time="2018-02-02",
            file_reader=_custom_cdf_loader)
        self.assertIsNotNone(v)
        self.assertTrue(v.meta.get("_custom_cdf_loader"))

    @data(
        "https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3/1min/2018/erg_pwe_hfa_l3_1min_20180102_v05_11.cdf",
        "http://themis.ssl.berkeley.edu/data/themis/thb/l2/gmom/0000/thb_l2_gmom_00000000_v01.cdf",
        "https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/erg_orb_l3_t89_00000000_v01.cdf"

    )
    def test_build_inventory_from_remote_cdf(self, url):
        parameters = extract_parameters(
            url_or_istp_loader=url,
            provider="test")
        self.assertGreater(len(parameters), 0)

    def test_build_inventory_from_remote_cdf_cda_trick(self):
        parameters = extract_parameters(
            url_or_istp_loader="https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/wi_sfsp_3dp_00000000_v01.cdf",
            provider="cda",
            enable_cda_trick=True
        )
        self.assertGreater(len(parameters), 0)
        for p in parameters:
            if p.spz_name() == "FLUX":
                self.assertEqual(p.VIRTUAL.lower(), "true")

    @data(
        # (spz.inventories.data_tree.archive.cda.Arase_ERG.PWE.HFA.erg_pwe_hfa_l3_1min.ne_mgf, "2018-01-06T10",
        # "2018-01-06T12"),
        ("archive/cda/Arase_ERG/PWE/HFA/erg_pwe_hfa_l3_1min/ne_mgf", "2018-01-06T10", "2018-01-06T12"),
        ("archive/cda/Arase_ERG/PWE/HFA/erg_pwe_hfa_l3_1min/ne_mgf", "2018-01-01T10", "2018-01-01T12"),
        ("archive/cda/MMS/MMS1/FPI/BURST/MOMS/mms1_fpi_brst_l2_des_moms/mms1_des_energyspectr_mz_brst", "2018-01-30T10",
         "2018-02-01T12"),
        ("archive/cda/MMS/MMS1/FPI/BURST/MOMS/mms1_fpi_brst_l2_des_moms/mms1_des_temppara_brst", "2018-02-28",
         "2018-03-02")

    )
    @unpack
    def test_get_data(self, product, start, stop):
        v = spz.get_data(product, start, stop)
        self.assertIsNotNone(v)

    @data(
        ("archive/cda/MMS/MMS1/FGM/SRVY/mms1_fgm_srvy_l2/mms1_fgm_b_bcs_srvy_l2",
         "2019-08-19",
         "2019-08-25"),
    )
    @unpack
    def test_get_data_with_no_file(self, product, start, stop):
        v = spz.get_data(product, start, stop)
        self.assertIsNone(v)

    @data(
        ("archive/cda/MMS/MMS1/FGM/SRVY/mms1_fgm_srvy_l2/mms1_fgm_b_bcs_srvy_l2",
         "2010-08-19",
         "2010-08-25"),
        ("archive/cda/MMS/MMS1/FPI/BURST/MOMS/mms1_fpi_brst_l2_des_moms/mms1_des_temppara_brst",
         "2006-02-28",
         "2006-03-02"),
        ("archive/cda/MMS/MMS1/FPI/FAST/MOMS/mms1_fpi_fast_l2_des_moms/mms1_des_energyspectr_omni_fast",
         "2010-01-30T10",
         "2010-02-01T12"),
    )
    @unpack
    def test_get_data_outside_of_range(self, product, start, stop):
        v = spz.get_data(product, start, stop)
        self.assertIsNone(v)

    def test_axes_merging_across_files(self):
        v = spz.get_data("archive/cda/MMS/MMS1/FPI/FAST/MOMS/mms1_fpi_fast_l2_des_moms/mms1_des_energyspectr_omni_fast",
                         "2018-01-05",
                         "2018-01-07")
        self.assertIsNotNone(v)
        self.assertEqual(len(v), len(v.axes[1]))

    def test_map_ranges_simple_case(self):
        ranges = dad.map_ranges(
            url="https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/ace/mag/level_2_cdaweb/mfi_h0/2010/.*.cdf",
            fname_regex=r"ac_h0_mfi_(?P<start>\d+)_v(?P<version>\d+).cdf",
            date_format="%Y%m%d", force_refresh=True)
        self.assertEqual(len(ranges), 365)
        self.assertEqual(ranges[0][1], (make_utc_datetime("2010-01-01"), make_utc_datetime("2010-01-02")))
        self.assertEqual(ranges[-1][1], (make_utc_datetime("2010-12-31"), None))

    def test_map_ranges_burst_files(self):
        ranges = dad.map_ranges(
            url="https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/mms/mms1/scm/brst/l2/schb/2021/07/.*.cdf",
            fname_regex=r"mms1_scm_brst_l2_schb_(?P<start>\d+)_v(?P<version>[\d\.]+).cdf",
            date_format="%Y%m%d%H%M%S", force_refresh=True)
        self.assertEqual(len(ranges), 841)
        self.assertEqual(ranges[0][1],
                         (make_utc_datetime("2021-07-01T00:03:43"), make_utc_datetime("2021-07-01T01:13:13")))
        self.assertEqual(ranges[-1][1],
                         (make_utc_datetime("2021-07-31T23:58:33"), None))

    def test_map_ranges_with_start_and_stop_in_filename(self):
        ranges = dad.map_ranges(
            url="https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/solar-orbiter/swa/science/l2/eas1-tm3d-psd/2024/.*cdf",
            fname_regex=r"solo_l2_swa-eas1-tm3d-psd_(?P<start>\d+t\d+)-(?P<stop>\d+t\d+)_v(?P<version>\d+)\.cdf",
            date_format="%Y%m%dT%H%M%S",
            force_refresh=True)
        self.assertEqual(len(ranges), 256)
        self.assertEqual(ranges[0][1],
                         (make_utc_datetime("2024-01-04T05:31:42"), make_utc_datetime("2024-01-04T05:36:40")))


if __name__ == '__main__':
    unittest.main()
