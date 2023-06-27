#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import re
import unittest
import os
from ddt import ddt, data
from datetime import datetime
from speasy.core.cache import drop_item
from speasy.core.any_files import any_loc_open, list_files

_HERE_ = os.path.dirname(os.path.abspath(__file__))


@ddt
class FileAccess(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_remote_txt_file(self):
        f = any_loc_open("http://sciqlop.lpp.polytechnique.fr/cache", mode='r')
        self.assertIsNotNone(f)
        self.assertIn('<title>SPEASY proxy</title>', f.read())

    def test_cached_remote_txt_file(self):
        drop_item("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html")
        start = datetime.now()
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html", mode='r',cache_remote_files=True)
        mid = datetime.now()
        self.assertIn('<!DOCTYPE html>', f.read())
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/jeandet/Vbias.html", mode='r',cache_remote_files=True)
        stop = datetime.now()
        self.assertIn('<!DOCTYPE html>', f.read())
        self.assertIsNotNone(f)
        self.assertGreater((mid - start)/4, stop - mid)

    def test_simple_remote_bin_file(self):
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw", mode='rb')
        self.assertIsNotNone(f)
        self.assertEquals(b'\x7fELF', f.read(4))

    def test_cached_remote_bin_file(self):
        drop_item("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw")
        start = datetime.now()
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw", mode='rb',
                         cache_remote_files=True)
        mid = datetime.now()
        self.assertEquals(b'\x7fELF', f.read(4))
        f = any_loc_open("https://hephaistos.lpp.polytechnique.fr/data/LFR/SW/LFR-FSW/3.0.0.0/fsw", mode='rb',
                         cache_remote_files=True)
        stop = datetime.now()
        self.assertEquals(b'\x7fELF', f.read(4))
        self.assertIsNotNone(f)
        self.assertGreater((mid - start)/4, stop - mid)

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

    @data(
        f"{_HERE_}/resources/",
        f"file://{_HERE_}/resources/"
    )
    def test_list_local_files(self, url):
        flist = list_files(url=url, file_regex=re.compile(r'\w+\.(txt|xml)'))
        self.assertGreaterEqual(len(flist), 4)
        self.assertIn('obsdatatree.xml', flist)
