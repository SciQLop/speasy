#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.core.http` package."""

import unittest
import os
from ddt import ddt, data, unpack

from speasy.core.http import is_server_up

_HERE_ = os.path.dirname(os.path.abspath(__file__))


@ddt
class HttpTests(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass


    @data(
        ("http://somewhere-that-does-not-exist-404.com", False),
        ("https://hephaistos.lpp.polytechnique.fr", True),
        ("http://sciqlop.lpp.polytechnique.fr:8080/", False),
    )
    @unpack
    def test_is_up(self, url, expected):
        self.assertEqual(is_server_up(url), expected)


if __name__ == '__main__':
    unittest.main()
