import os
import unittest

from ddt import ddt, data, unpack

from speasy.core.cdf.inventory_extractor import extract_parameters
from speasy.core.direct_archive_downloader.direct_archive_downloader import get_product


@ddt
class DirectArchiveDownloader(unittest.TestCase):
    def setUp(self):
        if "GITHUB_ACTION" in os.environ and os.environ.get("RUNNER_OS") == "Windows":
            self.skipTest("skip weirdly failing tests on windows")

    @data(
        (
            "https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3_1min/{Y}/erg_pwe_hfa_l3_1min_{Y}{M:02d}{D:02d}_v03_05.cdf",
            "daily", "ne_mgf", "2018-02-01", "2018-02-02"),
        ("http://themis.ssl.berkeley.edu/data/themis/thb/l2/scm/{Y}/thb_l2_scm_{Y}{M:02d}{D:02d}_v01.cdf",
         "daily", "thb_scf_gse", "2008-07-23T10", "2008-07-23T15"),
    )
    @unpack
    def test_download_existing_data(self, url_pattern, split_rule, variable, start_time, stop_time):
        data = get_product(
            url_pattern=url_pattern,
            split_rule=split_rule,
            variable=variable, start_time=start_time, stop_time=stop_time)
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
