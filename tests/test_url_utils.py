#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import re
import unittest
import os
from ddt import ddt, data, unpack

from speasy.core.url_utils import ensure_url_scheme, is_local_file

_HERE_ = os.path.dirname(os.path.abspath(__file__))


@ddt
class UrlUtils(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ("/home/test/files.txt", True),
        ("file:///home/test/files.txt", True),
        ("C:\\home\\test\\files.txt", True),
        ("file://C:\\home\\test\\files.txt", True),
        ("http://somewhere.com", False),
        ("https://somewhere.com", False),
        ("https://somewhere.com/", False),
        ("https://somewhere.com/test", False)
    )
    @unpack
    def test_is_local_file(self, url, is_local):
        self.assertEqual(is_local_file(url), is_local)

    @data(
        ("/home/test/files.txt", "file:///home/test/files.txt"),
        ("file:///home/test/files.txt", "file:///home/test/files.txt"),
        ("C:\\home\\test\\files.txt", "file://C:\\home\\test\\files.txt"),
        ("file://C:\\home\\test\\files.txt", "file://C:\\home\\test\\files.txt"),
        ("http://somewhere.com", "http://somewhere.com"),
        ("https://somewhere.com", "https://somewhere.com"),
        ("https://somewhere.com/", "https://somewhere.com/"),
        ("https://somewhere.com/test", "https://somewhere.com/test")
    )
    @unpack
    def test_ensure_url_scheme(self, url, expected_url):
        self.assertEqual(ensure_url_scheme(url), expected_url)


if __name__ == '__main__':
    unittest.main()
