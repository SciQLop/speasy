import unittest
from multiprocessing import Pool
from ddt import ddt, data, unpack

import speasy as spz
from speasy.core import make_utc_datetime
from speasy.core.cdf.inventory_extractor import extract_parameters
from speasy.core.direct_archive_downloader import get_product
from speasy.core.direct_archive_downloader.direct_archive_downloader import spilt_range, _read_cdf, map_ranges


def _custom_cdf_loader(url, variable, *args, **kwargs):
    v = _read_cdf(url, variable, *args, **kwargs)
    v.meta["_custom_cdf_loader"] = True
    return v


@ddt
class DirectArchiveDownloader(unittest.TestCase):
    def setUp(self):
        pass

    def test_split_rules(self):
        self.assertListEqual(spilt_range(split_frequency='daily', start_time='2010-01-01', stop_time='2010-01-01'),
                             [make_utc_datetime('2010-01-01')]
                             )
        self.assertListEqual(spilt_range(split_frequency='monthly', start_time='2010-01-01', stop_time='2010-01-01'),
                             [make_utc_datetime('2010-01-01')]
                             )
        self.assertListEqual(spilt_range(split_frequency='yearly', start_time='2010-01-01', stop_time='2010-01-01'),
                             [make_utc_datetime('2010-01-01')]
                             )

        self.assertListEqual(spilt_range(split_frequency='daily', start_time='2010-01-01', stop_time='2010-01-02'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-01-02')]
                             )
        self.assertListEqual(spilt_range(split_frequency='monthly', start_time='2010-01-01', stop_time='2010-02-01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-02-01')]
                             )
        self.assertListEqual(spilt_range(split_frequency='yearly', start_time='2010-01-01', stop_time='2011-01-01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2011-01-01')]
                             )

        self.assertListEqual(spilt_range(split_frequency='daily', start_time='2010-01-01', stop_time='2010-01-02T01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-01-02')]
                             )
        self.assertListEqual(spilt_range(split_frequency='monthly', start_time='2010-01-01', stop_time='2010-02-01T01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2010-02-01')]
                             )
        self.assertListEqual(spilt_range(split_frequency='yearly', start_time='2010-01-01', stop_time='2011-01-01T01'),
                             [make_utc_datetime('2010-01-01'), make_utc_datetime('2011-01-01')]
                             )

    def test_unknown_split_rules_raises(self):
        with self.assertRaises(ValueError):
            spilt_range(split_frequency='unknown', start_time='2010-01-01', stop_time='2011-01-01')

    @data(
        (
                "https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3/1min/{Y}/erg_pwe_hfa_l3_1min_{Y}{M:02d}{D:02d}_v04_09.cdf",
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

    def test_get_product_with_custom_loader(self):
        v = get_product(
            url_pattern="https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3/1min/{Y}/erg_pwe_hfa_l3_1min_{Y}{M:02d}{D:02d}_v04_09.cdf",
            split_rule="regular",
            variable="ne_mgf", start_time="2018-02-01", stop_time="2018-02-02",
            file_reader=_custom_cdf_loader)
        self.assertIsNotNone(v)
        self.assertTrue(v.meta.get("_custom_cdf_loader"))

    @data(
        "https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3/1min/2018/erg_pwe_hfa_l3_1min_20180102_v04_09.cdf",
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
        ranges = map_ranges(
            url="https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/ace/mag/level_2_cdaweb/mfi_h0/2010/.*.cdf",
            fname_regex=r"ac_h0_mfi_(?P<start>\d+)_v(?P<version>\d+).cdf",
            date_format="%Y%m%d", force_refresh=True)
        self.assertEqual(len(ranges), 365)
        self.assertEqual(ranges[0][1], (make_utc_datetime("2010-01-01"), make_utc_datetime("2010-01-02")))
        self.assertEqual(ranges[-1][1], (make_utc_datetime("2010-12-31"), None))

    def test_map_ranges_burst_files(self):
        ranges = map_ranges(
            url="https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/mms/mms1/scm/brst/l2/schb/2021/07/.*.cdf",
            fname_regex=r"mms1_scm_brst_l2_schb_(?P<start>\d+)_v(?P<version>[\d\.]+).cdf",
            date_format="%Y%m%d%H%M%S", force_refresh=True)
        self.assertEqual(len(ranges), 841)
        self.assertEqual(ranges[0][1],
                         (make_utc_datetime("2021-07-01T00:03:43"), make_utc_datetime("2021-07-01T01:13:13")))
        self.assertEqual(ranges[-1][1],
                         (make_utc_datetime("2021-07-31T23:58:33"), None))

    def test_map_ranges_with_start_and_stop_in_filename(self):
        ranges = map_ranges(
            url="https://sciqlop.lpp.polytechnique.fr/cdaweb-data/pub/data/solar-orbiter/swa/science/l2/eas1-tm3d-psd/2024/.*cdf",
            fname_regex=r"solo_l2_swa-eas1-tm3d-psd_(?P<start>\d+t\d+)-(?P<stop>\d+t\d+)_v(?P<version>\d+)\.cdf",
            date_format="%Y%m%dT%H%M%S",
            force_refresh=True)
        self.assertEqual(len(ranges), 256)
        self.assertEqual(ranges[0][1],
                         (make_utc_datetime("2024-01-04T05:31:42"), make_utc_datetime("2024-01-04T05:36:40")))


if __name__ == '__main__':
    unittest.main()
