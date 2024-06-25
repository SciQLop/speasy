#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import os
import re
import unittest
from datetime import datetime
import time

from ddt import ddt, data

from speasy.core.any_files import any_loc_open, list_files
from speasy.core.cache import drop_item
from multiprocessing import Value, Process

_HERE_ = os.path.dirname(os.path.abspath(__file__))


def _open_file(url, value):
    value.value -= 1
    while value.value > 0:
        time.sleep(.01)
    any_loc_open(url, mode='r', cache_remote_files=True)


@ddt
class FileAccess(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_remote_txt_file(self):
        f = any_loc_open("http://sciqlop.lpp.polytechnique.fr/cache/", mode='r')
        self.assertIsNotNone(f)
        self.assertIn('<title>Speasy Cache Server</title>', f.read())

    def test_cached_remote_txt_file(self):
        drop_item("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html")
        start = datetime.now()
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html", mode='r',
                         cache_remote_files=True)
        mid = datetime.now()
        self.assertIn('<!DOCTYPE html>', f.read())
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html", mode='r',
                         cache_remote_files=True)
        stop = datetime.now()
        self.assertIn('<!DOCTYPE html>', f.read())
        self.assertIsNotNone(f)
        self.assertGreater(mid - start, stop - mid)

    def test_simple_remote_bin_file(self):
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw", mode='rb')
        self.assertIsNotNone(f)
        self.assertEqual(b'\x7fELF', f.read(4))

    def test_simple_remote_bin_file_with_rewrite_rules(self):
        if 'SPEASY_CORE_HTTP_REWRITE_RULES' not in os.environ:
            self.skipTest("No rewrite rules defined")
        f = any_loc_open(
            "https://thisserver_does_not_exists.lpp.polytechnique.fr/pub/data/ace/mag/level_2_cdaweb/mfi_h0/2014/ac_h0_mfi_20141117_v06.cdf",
            mode='rb')
        self.assertIsNotNone(f)
        self.assertIn(b'NSSDC Common Data Format', f.read(100))

    def test_cached_remote_bin_file(self):
        drop_item("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw")
        start = datetime.now()
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw", mode='rb',
                         cache_remote_files=True)
        mid = datetime.now()
        self.assertEqual(b'\x7fELF', f.read(4))
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw", mode='rb',
                         cache_remote_files=True)
        stop = datetime.now()
        self.assertEqual(b'\x7fELF', f.read(4))
        self.assertIsNotNone(f)
        self.assertGreater(mid - start, stop - mid)

    def test_remote_file_request_deduplication(self):
        drop_item("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html")
        sync = Value('i', 5)
        try:
            processes = [Process(target=_open_file, args=(
                "https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html", sync)) for _ in range(4)]
            for p in processes:
                p.start()
            _open_file("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html", sync)
        finally:
            for p in processes:
                p.join()
            self.assertEqual(0, sync.value)

    @data(
        f"{_HERE_}/resources/derived_param.txt",
        f"file://{_HERE_}/resources/derived_param.txt"
    )
    def test_simple_local_txt_file(self, url):
        f = any_loc_open(url, mode='r')
        self.assertIsNotNone(f)
        self.assertIn('AMDA INFO', f.read(100))

    def test_list_remote_files(self):
        flist = list_files(url='https://hephaistos.lpp.polytechnique.fr/data/', file_regex=re.compile(r'\w+\.webm'))
        self.assertGreaterEqual(len(flist), 9)
        self.assertIn('plasmaSpeaker1.webm', flist)

    def test_list_remote_files_with_rewrite_rules(self):
        if 'SPEASY_CORE_HTTP_REWRITE_RULES' not in os.environ:
            self.skipTest("No rewrite rules defined")
        flist = list_files(
            url='https://thisserver_does_not_exists.lpp.polytechnique.fr/pub/data/ace/mag/level_2_cdaweb/mfi_h0/2014/',
            file_regex=re.compile(r'.*\.cdf'))
        self.assertGreaterEqual(len(flist), 10)

    @data(
        f"{_HERE_}/resources/",
        f"file://{_HERE_}/resources/"
    )
    def test_list_local_files(self, url):
        flist = list_files(url=url, file_regex=re.compile(r'\w+\.(txt|xml)'))
        self.assertGreaterEqual(len(flist), 4)
        self.assertIn('obsdatatree.xml', flist)


if __name__ == '__main__':
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    unittest.main()
