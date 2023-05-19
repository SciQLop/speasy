import os
import unittest

from ddt import ddt

from speasy.core.cdf.inventory_extractor import extract_parameters
from speasy.core.direct_archive_downloader.direct_archive_downloader import get_product


@ddt
class CDADirectArchiveDownloader(unittest.TestCase):
    def setUp(self):
        if "GITHUB_ACTION" in os.environ and os.environ.get("RUNNER_OS") == "Windows":
            self.skipTest("skip weirdly failing tests on windows")

    def test_download_existing_data(self):
        data = get_product(
            url_pattern="https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3_1min/{Y}/erg_pwe_hfa_l3_1min_{Y}{M:02d}{D:02d}_v03_05.cdf",
            split_rule="daily",
            variable="ne_mgf", start_time="2018-02-01", stop_time="2018-02-02")
        self.assertIsNotNone(data)

    def test_build_inventory_from_remote_cdf(self):
        parameters = extract_parameters(
            url="https://cdaweb.gsfc.nasa.gov/pub/data/arase/pwe/hfa/l3_1min/2018/erg_pwe_hfa_l3_1min_20180102_v03_05.cdf",
            provider="test")
        self.assertGreater(len(parameters), 0)

    def test_build_inventory_from_remote_master_cdf(self):
        parameters = extract_parameters(
            url="https://cdaweb.gsfc.nasa.gov/pub/software/cdawlib/0MASTERS/erg_orb_l3_t89_00000000_v01.cdf",
            provider="test")
        self.assertGreater(len(parameters), 0)
