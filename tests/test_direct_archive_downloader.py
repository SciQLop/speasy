import unittest

from ddt import ddt, data, unpack

import speasy as spz
from speasy.core.cdf.inventory_extractor import extract_parameters
from speasy.core.direct_archive_downloader.direct_archive_downloader import get_product


@ddt
class DirectArchiveDownloader(unittest.TestCase):
    def setUp(self):
        pass

    @data(
        (
            "https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3_1min/{Y}/erg_pwe_hfa_l3_1min_{Y}{M:02d}{D:02d}_v03_05.cdf",
            "regular", "ne_mgf", "2018-02-01", "2018-02-02"),
        (
            "http://themis.ssl.berkeley.edu/data/themis/thb/l2/scm/{Y}/thb_l2_scm_{Y}{M:02d}{D:02d}_v01.cdf",
            "regular", "thb_scf_gse", "2008-07-23T10", "2008-07-23T15"),
        (
            "https://cdaweb.gsfc.nasa.gov/pub/data/solar-orbiter/rpw/low_latency/ll02/sbm1/{Y}/solo_ll02_rpw-sbm1_{Y}{M:02d}{D:02d}t\d+-\d+t\d+_v\d+u.cdf",
            "random", "DT1_SBM1", "2021-07-23T10", "2021-07-25T23",
            {'fname_regex': 'solo_ll02_rpw-sbm1_(?P<start>\d+t\d+)-(?P<stop>\d+t\d+)_v(?P<version>\d+)u\.cdf'}),
    )
    @unpack
    def test_download_existing_data(self, url_pattern, split_rule, variable, start_time, stop_time, kwargs=None):
        kwargs = kwargs or {}
        data = get_product(
            url_pattern=url_pattern,
            split_rule=split_rule,
            variable=variable, start_time=start_time, stop_time=stop_time, **kwargs)
        self.assertIsNotNone(data)

    @data(
        "https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3_1min/2018/erg_pwe_hfa_l3_1min_20180102_v03_05.cdf",
        "http://themis.ssl.berkeley.edu/data/themis/thb/l2/gmom/0000/thb_l2_gmom_00000000_v01.cdf",
        "https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/erg_orb_l3_t89_00000000_v01.cdf"

    )
    def test_build_inventory_from_remote_cdf(self, url):
        parameters = extract_parameters(
            url=url,
            provider="test")
        self.assertGreater(len(parameters), 0)

    @data(
        # (spz.inventories.data_tree.archive.cda.Arase_ERG.PWE.HFA.erg_pwe_hfa_l3_1min.ne_mgf, "2018-01-06T10",
        # "2018-01-06T12"),
        ("archive/cda/Arase_ERG/PWE/HFA/erg_pwe_hfa_l3_1min/ne_mgf", "2018-01-06T10", "2018-01-06T12"),
        ("archive/cda/Arase_ERG/PWE/HFA/erg_pwe_hfa_l3_1min/ne_mgf", "2018-01-01T10", "2018-01-01T12"),
        ("archive/cda/MMS/MMS1/FPI/BURST/MOMS/mms1_fpi_brst_l2_des_moms/mms1_des_energyspectr_mz_brst", "2018-01-01T10",
         "2018-01-01T12")

    )
    @unpack
    def test_get_data(self, product, start, stop):
        v = spz.get_data(product, start, stop)
        self.assertIsNotNone(v)
