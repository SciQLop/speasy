#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy.common` package."""
import unittest
import speasy.common as com
from ddt import ddt, data, unpack


@ddt
class Listify(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @data(
        ("some text", ["some text"]),
        ([1], [1]),
        ((1, 2), [1, 2])
    )
    @unpack
    def test_listify(self, input, expected):
        self.assertEqual(com.listify(input), expected)
