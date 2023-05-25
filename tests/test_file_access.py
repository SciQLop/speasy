#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import unittest

from ddt import ddt, data

from speasy.core.file_access import get, head


@ddt
class FileAccess(unittest.TestCase):
    def setUp(self):
        self.skipTest('Needs testable urls')

    def tearDown(self):
        pass

    @data(
        'http://amdadev.irap.omp.eu/php/rest/test.php?type=429',
        'http://amdadev.irap.omp.eu/php/rest/test.php?type=429&delay=5',
        'http://amdadev.irap.omp.eu/php/rest/test.php?type=503&delay=5'
    )
    def test_get_retry(self, url):
        self.assertIsNotNone(get(url))

    @data(
        'http://amdadev.irap.omp.eu/php/rest/test.php?type=429',
        'http://amdadev.irap.omp.eu/php/rest/test.php?type=429&delay=5',
        'http://amdadev.irap.omp.eu/php/rest/test.php?type=503&delay=5'
    )
    def test_head_retry(self, url):
        self.assertIsNotNone(head(url))
