import os
import unittest

from ddt import ddt

from speasy.webservices.cda.direct_archive_downloader import get_product


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
